import math

def linear(x):
    return x


def ease_in_out_quad(x):
    return 2 * x * x if x < 0.5 else 1 - math.pow(-2 * x + 2, 2) / 2


def ease_in_out_expo(x):
    if x == 0.0:
        return 0.0

    if x == 1:
        return 1.0

    if x < 0.5:
        return math.pow(2.0, 20.0 * x - 10.0) / 2.0
    else:
        return (2.0 - math.pow(2.0, -20 * x + 10.0)) / 2.0


def interp(x0, x1, t, func):
    return x0 + (x1 - x0) * func(t)