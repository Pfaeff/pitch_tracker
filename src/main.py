import sys
import os
import copy
import math
import multiprocessing
import configparser

import numpy as np

import pygame
import pygame.freetype
import pygame.gfxdraw
from pygame._sdl2.video import Window

from pitch_tracker import PitchTracker, list_audio_devices
import note_helper
import interpolation

VERSION = "V0.2"

# def draw_line(surface, color, x0, x1, thickness=1):
#     center_L1 = (np.array(x0) + np.array(x1)) / 2
#     length = np.linalg.norm(np.array(x0) - np.array(x1))
#     angle = math.atan2(x0[1] - x1[1], x0[0] - x1[0])

#     UL = (center_L1[0] + (length / 2) * math.cos(angle) - (thickness / 2) * math.sin(angle),
#         center_L1[1] + (thickness / 2) * math.cos(angle) + (length / 2) * math.sin(angle))
#     UR = (center_L1[0] - (length / 2) * math.cos(angle) - (thickness / 2) * math.sin(angle),
#         center_L1[1] + (thickness / 2) * math.cos(angle) - (length / 2) * math.sin(angle))
#     BL = (center_L1[0] + (length / 2) * math.cos(angle) + (thickness / 2) * math.sin(angle),
#         center_L1[1] - (thickness / 2) * math.cos(angle) + (length / 2) * math.sin(angle))
#     BR = (center_L1[0] - (length / 2) * math.cos(angle) + (thickness / 2) * math.sin(angle),
#         center_L1[1] - (thickness / 2) * math.cos(angle) - (length / 2) * math.sin(angle))    

#     pygame.gfxdraw.aapolygon(surface, (UL, UR, BR, BL), color)
#     pygame.gfxdraw.filled_polygon(surface, (UL, UR, BR, BL), color)


# def draw_lines(surface, color, closed, coords, thickness=1):
#     if len(coords) < 2:
#         return

#     for i in range(1, len(coords)):
#         draw_line(surface, color, coords[i-1], coords[i], thickness)

#     if closed:
#         draw_line(surface, color, coords[-1], coords[0], thickness)


class PitchTrackerGraph:

    HIGHEST_PITCH_TO_DISPLAY = 2000.0   # in Hz 

    ANIMATION_DURATION = 0.5            # in seconds

    DEFAULT_FONT_SIZE = 18 # doesn't really matter, since it will be computed on-the-fly
    TEXT_MARGIN = 0.2
    MIN_FONT_SIZE = 16
    MAX_FONT_SIZE = 32

    MIN_OCCURENCE_AGAINST_OUTLIERS = 10 # Outlier detection to prevent erratic scaling behaviour

    BACKGROUND_COLOR = (32, 32, 32)    
    NOTE_LINE_COLOR = (160, 160, 160)
    SHARP_NOTE_LINE_COLOR = (96, 96, 96)
    C_NOTE_LINE_COLOR = (255, 255, 255)
    FOREGROUND_LINE_COLOR = (255, 165, 0)

    EXPONENTIAL_SCALING = False         # If False, notes will be spaced equally for all frequencies


    def __init__(self, screen, bounds, standard_pitch):
        self.screen = screen
        self.bounds = bounds
        self.surface = pygame.Surface(self.bounds[2:4])
        self.standard_pitch = standard_pitch

        self.note_column_font = pygame.freetype.SysFont('Sans', PitchTrackerGraph.DEFAULT_FONT_SIZE)       
        text_rect = self.note_column_font.get_rect("W")      
        self.default_font_height = text_rect.height   

        lowest_note = note_helper.note_name_to_value("E2")
        self.lowest_note_on_display = lowest_note
        self.lowest_note_on_display_target = self.lowest_note_on_display
        self.lowest_frequency_on_display = note_helper.note_to_frequency(lowest_note, self.standard_pitch)
        self.lowest_frequency_on_display_previous = self.lowest_frequency_on_display
        self.lowest_frequency_on_display_target = self.lowest_frequency_on_display

        highest_note = note_helper.note_name_to_value("E4")
        self.highest_note_on_display = highest_note
        self.highest_note_on_display_target = self.highest_note_on_display
        self.highest_frequency_on_display = note_helper.note_to_frequency(highest_note, self.standard_pitch)
        self.highest_frequency_on_display_previous = self.highest_frequency_on_display
        self.highest_frequency_on_display_target = self.highest_frequency_on_display

        self.camera_lerp = 0.0


    def resize(self, size):
        self.bounds = (*self.bounds[0:2], *size[0:2])
        self.surface = pygame.Surface(self.bounds[2:4])        


    def note_value_to_y_coord(self, note):
        frequency = note_helper.note_to_frequency(note, self.standard_pitch)

        return self.frequency_to_y_coord(frequency)


    def frequency_to_y_coord(self, freq):
        _, surface_height = self.surface.get_size()

        low  = self.lowest_frequency_on_display
        high = self.highest_frequency_on_display

        if not PitchTrackerGraph.EXPONENTIAL_SCALING:
            low = note_helper.frequency_to_note(low, self.standard_pitch, False)
            high = note_helper.frequency_to_note(high, self.standard_pitch, False)
            freq = note_helper.frequency_to_note(freq, self.standard_pitch, False)

        range_frequencies_on_display = high - low

        if range_frequencies_on_display == 0:
            return 0

        return surface_height - (surface_height *  (freq - low) / range_frequencies_on_display)


    def update_camera_bounds(self, analysis_results):
        note_values = [note_helper.frequency_to_note(result[1], self.standard_pitch) for result in analysis_results]

        occurrences = {x : note_values.count(x) for x in set(note_values)}

        lowest_pitch = float("inf")
        highest_pitch = 0.0

        for _, pitch, _, _, _ in analysis_results:
            note_value = note_helper.frequency_to_note(pitch, self.standard_pitch)
            if pitch > 0.0 and pitch <= PitchTrackerGraph.HIGHEST_PITCH_TO_DISPLAY and occurrences[note_value] > PitchTrackerGraph.MIN_OCCURENCE_AGAINST_OUTLIERS:
                if pitch < lowest_pitch:
                    lowest_pitch = pitch
                if pitch > highest_pitch:
                    highest_pitch = pitch

        if highest_pitch > lowest_pitch:
            new_lowest_pitch = note_helper.frequency_to_note(lowest_pitch, self.standard_pitch) - 1
            new_highest_pitch = note_helper.frequency_to_note(highest_pitch, self.standard_pitch) + 1

            if (new_lowest_pitch != self.lowest_note_on_display_target) or (new_highest_pitch != self.highest_note_on_display_target):
                self.lowest_frequency_on_display_previous = self.lowest_frequency_on_display
                self.highest_frequency_on_display_previous = self.highest_frequency_on_display

                self.lowest_frequency_on_display_target = note_helper.note_to_frequency(new_lowest_pitch)
                self.highest_frequency_on_display_target = note_helper.note_to_frequency(new_highest_pitch)

                self.lowest_note_on_display_target = note_helper.frequency_to_note(self.lowest_frequency_on_display_target)
                self.highest_note_on_display_target = note_helper.frequency_to_note(self.highest_frequency_on_display_target)        

                self.camera_lerp = 0.0    


    def update_camera(self, delta_t):
        self.camera_lerp += delta_t / PitchTrackerGraph.ANIMATION_DURATION   
        if self.camera_lerp > 1.0:
            self.camera_lerp = 1.0

        self.lowest_frequency_on_display = interpolation.interp(self.lowest_frequency_on_display_previous, 
                                                                self.lowest_frequency_on_display_target, 
                                                                self.camera_lerp, interpolation.ease_in_out_expo)     

        self.highest_frequency_on_display = interpolation.interp(self.highest_frequency_on_display_previous, 
                                                                 self.highest_frequency_on_display_target, 
                                                                 self.camera_lerp, interpolation.ease_in_out_expo)  

        self.lowest_note_on_display = note_helper.frequency_to_note(self.lowest_frequency_on_display)
        self.highest_note_on_display = note_helper.frequency_to_note(self.highest_frequency_on_display)

        self.num_notes_on_display = self.highest_note_on_display - self.lowest_note_on_display 


    def run(self, delta_t):
        self.update_camera(delta_t)        


    def render(self, pitch_tracker):
        analysis_results = copy.deepcopy(pitch_tracker.get_analysis_results())

        if len(analysis_results) == 0:
            return

        self.surface.fill(PitchTrackerGraph.BACKGROUND_COLOR)

        surface_width, surface_height = self.surface.get_size()

        self.update_camera_bounds(analysis_results)          

        # Font scaling
        space_per_note = 0.5 * surface_height / self.num_notes_on_display
        font_scaling = space_per_note / self.default_font_height
        new_font_size = PitchTrackerGraph.DEFAULT_FONT_SIZE * font_scaling
        if new_font_size < PitchTrackerGraph.MIN_FONT_SIZE:
            new_font_size = PitchTrackerGraph.MIN_FONT_SIZE
        if new_font_size > PitchTrackerGraph.MAX_FONT_SIZE:
            new_font_size = PitchTrackerGraph.MAX_FONT_SIZE
        self.note_column_font = pygame.freetype.SysFont('Sans', new_font_size)       

        # Draw note names
        note_column_end = 0
        names_y_coords_and_colors = []
        for i in range(self.num_notes_on_display):
            y = self.note_value_to_y_coord(self.lowest_note_on_display + i)
            note_name = note_helper.value_to_note_name(self.lowest_note_on_display + i)

            color = PitchTrackerGraph.NOTE_LINE_COLOR
            if "#" in note_name:
                color = PitchTrackerGraph.SHARP_NOTE_LINE_COLOR
            elif "C" in note_name:
                color = PitchTrackerGraph.C_NOTE_LINE_COLOR            

            names_y_coords_and_colors.append((note_name, y, color))

            text_rect = self.note_column_font.get_rect(note_name)

            text_position = PitchTrackerGraph.TEXT_MARGIN * text_rect.width

            if y >= 0 and y < surface_height:
                dest = (text_position, y - text_rect.height // 2)
                if dest[1] >= 0:
                    self.note_column_font.render_to(self.surface, 
                                                    dest, 
                                                    note_name,
                                                    color)

                note_column_end = max(note_column_end, text_position + (1.0 + PitchTrackerGraph.TEXT_MARGIN) * text_rect.width)

        # Draw note lines
        for note_name, y, color in names_y_coords_and_colors:
            pygame.draw.line(self.surface, 
                             color, 
                             (note_column_end, y), 
                             (surface_width - 1, y))

        # Draw curve
        if (len(analysis_results) > 1):
            coords = []

            for i in range(len(analysis_results)):
                pitch = analysis_results[i][1]

                if (pitch <= 0.0) or (pitch > PitchTrackerGraph.HIGHEST_PITCH_TO_DISPLAY): 
                    if len(coords) > 1:
                        pygame.draw.aalines(self.surface, 
                                            PitchTrackerGraph.FOREGROUND_LINE_COLOR, 
                                            False,
                                            coords)                            

                    coords = []
                    continue
                
                x = (i / pitch_tracker.analysis_window_len) * (surface_width - note_column_end) + note_column_end
                y = self.frequency_to_y_coord(analysis_results[i][1])

                coords.append((x, y))

            if len(coords) > 1: 
                pygame.draw.aalines(self.surface, 
                                    PitchTrackerGraph.FOREGROUND_LINE_COLOR, 
                                    False,
                                    coords)    

        self.screen.blit(self.surface, (self.bounds[0:2]))        


class Menu:

    def __init__(self, size):
        self.size = size


    def resize(self, new_size):
        pass


    def update(self, events):
        pass


    def render(self, surface):
        pass


class PitchTrackerUI:
    BACKGROUND_COLOR = (64, 64, 64)

    MENU_WIDTH_PERCENTAGE = 0.5
    MENU_HEIGHT_PERCENTAGE = 0.5

    def __init__(self, 
                 device_index, 
                 offset, 
                 resolution, 
                 target_fps, 
                 standard_pitch, 
                 silence_threshold, 
                 analysis_window, 
                 filter_window, 
                 start_in_fullscreen):
        pygame.init()

        self.offset = offset
        self.default_resolution = resolution
        self.target_fps = target_fps
        self.standard_pitch = standard_pitch
        self.silence_threshold = silence_threshold
        self.analysis_window = analysis_window
        self.filter_window = filter_window

        # Determine the resolution of the display
        info = pygame.display.Info()
        self.max_resolution = (info.current_w, info.current_h)

        self.screen = pygame.display.set_mode(self.default_resolution, pygame.RESIZABLE)
        self.previous_resolution = self.default_resolution
        self.is_fullscreen = False

        pygame.display.set_caption("Pitch Tracker - " + VERSION)

        icon = pygame.image.load("resources/icon.png")
        pygame.display.set_icon(icon)

        self.pitch_tracker = PitchTracker(device_index=device_index, 
                                          analysis_window=self.analysis_window, 
                                          filter_window=filter_window, 
                                          silence_threshold=self.silence_threshold)
        self.pitch_tracker.start_tracking()

        screen_width, screen_height = pygame.display.get_surface().get_size()
        self.pitch_tracker_graph = PitchTrackerGraph(self.screen, (0, 0, screen_width, screen_height), self.standard_pitch)

        self.menu = Menu(size=(int(screen_width * PitchTrackerUI.MENU_WIDTH_PERCENTAGE), 
                               int(screen_height * PitchTrackerUI.MENU_HEIGHT_PERCENTAGE)))

        self.clock = pygame.time.Clock()

        self.show_menu = False
        self.running = True

        if start_in_fullscreen:
            self.toggle_fullscreen()
        else:
            # Set initial window position using the offset specified in the configuration 
            self.reposition_window()

        self.main_loop()

    
    def set_silence_threshold(self, silence_threshold):
        self.silence_threshold = silence_threshold
        self.pitch_tracker.set_silence(self.silence_threshold)


    def set_audio_device(self, index):
        self.pitch_tracker.change_device(index)


    def reposition_window(self):
        actual_size = self.screen.get_size()
        window = Window.from_display_module()
        window.position = (self.max_resolution[0] // 2 - actual_size[0] // 2 + self.offset[0], 
                           self.max_resolution[1] // 2 - actual_size[1] // 2 + self.offset[1])


    def toggle_fullscreen(self):
        # pygame.display.toggle_fullscreen()
        if self.is_fullscreen:
            self.screen = pygame.display.set_mode(self.previous_resolution, pygame.RESIZABLE)  
            self.resize(self.previous_resolution)
        else:
            self.previous_resolution = self.screen.get_size()
            self.screen = pygame.display.set_mode(self.max_resolution, pygame.NOFRAME)  
            self.resize(self.max_resolution)
    
        # NOTE this uses an experimental API to reposition the window
        self.reposition_window()

        self.is_fullscreen = not self.is_fullscreen

    def resize(self, size):
        self.pitch_tracker_graph.resize(size)
        self.menu.resize((int(size[0] * PitchTrackerUI.MENU_WIDTH_PERCENTAGE), 
                          int(size[1] * PitchTrackerUI.MENU_HEIGHT_PERCENTAGE)))        


    def exit(self):
        if self.is_fullscreen:
            self.toggle_fullscreen()          
        self.pitch_tracker.stop_tracking()
        self.running = False          


    def main_loop(self):
        last_time = pygame.time.get_ticks()
        while self.running:
            current_time = pygame.time.get_ticks()
            self.delta_t = (current_time - last_time) / 1000.0
            last_time = current_time

            self.pitch_tracker_graph.run(self.delta_t)

            events = pygame.event.get()
            for event in events:
                if event.type == pygame.QUIT:
                    self.exit()  
                if (event.type == pygame.KEYDOWN):
                    if event.key == pygame.K_ESCAPE:
                        # self.show_menu = not self.show_menu
                        self.exit()
                    elif event.key == pygame.K_F11:
                        self.toggle_fullscreen()
                if event.type == pygame.VIDEORESIZE:
                    self.resize((event.w, event.h))

            self.menu.update(events)

            self.screen.fill(PitchTrackerUI.BACKGROUND_COLOR)
            self.pitch_tracker_graph.render(self.pitch_tracker)                        

            if self.show_menu:
                self.menu.render(self.screen)

            self.clock.tick(self.target_fps)
            pygame.display.update()

        pygame.quit()


def main(argv):
    device_index = 0
    standard_pitch = 440.0           
    analysis_window = 10.0   
    filter_window = 0.2       
    silence_threshold = -60.0

    offset_x = 0
    offset_y = 0
    default_width = 1024
    default_height = 768
    target_fps = 60
    start_in_fullscreen = False

    CONFIG_PATH = "config.cfg"

    if os.path.exists(CONFIG_PATH):
        config = configparser.ConfigParser()
        config.read(CONFIG_PATH)

        audio_settings = config['audio']
        device_index = int(audio_settings['InputDeviceId'])
        standard_pitch = float(audio_settings['StandardPitch'])
        analysis_window = float(audio_settings['AnalysisWindow'])
        filter_window = float(audio_settings['FilterWindow'])
        silence_threshold = float(audio_settings['SilenceThreshold'])

        graphics_settings = config['graphics']
        offset_x = int(graphics_settings['OffsetX'])
        offset_y = int(graphics_settings['OffsetY'])
        default_width = int(graphics_settings['DefaultWidth'])
        default_height = int(graphics_settings['DefaultHeight'])
        target_fps = int(graphics_settings['TargetFPS'])
        start_in_fullscreen = graphics_settings.getboolean('StartInFullscreen')

    print()
    print("PITCH TRACKER")
    print("=============")
    print()
    print("Version:", VERSION)
    print("Copyright: Kai Röhr (2020-)")
    print()
    print("CONFIGURATION")
    print("=============")
    print()
    print("Audio:")
    print("------")
    print("device_index:", device_index)
    print("standard_pitch:", standard_pitch)
    print("analysis_window:", analysis_window)
    print("filter_window:", filter_window)
    print("silence_threshold:", silence_threshold)
    print()
    print("Graphics:")
    print("---------")    
    print("offset_x:", offset_x)
    print("offset_y:", offset_y)
    print("default_width:", default_width)
    print("default_height:", default_height)
    print("target_fps:", target_fps)
    print("start_in_fullscreen:", start_in_fullscreen)
    print()

    PitchTrackerUI(device_index=device_index, 
                   offset=(offset_x, offset_y),
                   resolution=(default_width, default_height), 
                   target_fps=target_fps, 
                   standard_pitch=standard_pitch, 
                   silence_threshold=silence_threshold,
                   analysis_window=analysis_window,
                   filter_window=filter_window,
                   start_in_fullscreen=start_in_fullscreen)


if __name__ == "__main__": 
    # Pyinstaller fix
    multiprocessing.freeze_support()

    main(sys.argv)