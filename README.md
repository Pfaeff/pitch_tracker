![](logo_with_text.png)

# Real-time instrument or vocal pitch tracker - Version 0.2

## What it does

This app tracks pitch changes of a single instrument over time.
It can be useful for practising intonation, vibrato, slides and bends. It was built with singing in mind, but it works just as well with instruments such as the guitar or violin. 
You can also use it as a tuner.

## What it doesn't

It can't track multiple notes simultaneously or even detect chords. It might also not work if there is a lot of background noise.

## Download

[Windows](https://www.dropbox.com/s/vslhfspumk18gyu/PitchTracker_V0.2.zip?dl=1)

### Why is this over 250MB in size?

I didn't want to spend lots of time developing this, so I decided to use python and pyinstaller. 
This allowed me to write most of it in a single afternoon, but it also resulted in a fairly large executable.

## Installation

- Extract all files
- Run "PitchTracker.exe"

## Usage

Sing or play into your microphone or audio device. 
If it doesn't work, try changing the device id and silence threshold in the config file.

**Note:** This is still a very early version, so there likely will be some issues.

## Screenshot

![](screenshot.jpg)
