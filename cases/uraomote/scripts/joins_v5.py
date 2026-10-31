"""Every cut of animatic_v5 and how it joins (scripts/joins.py): slow sections dissolve, fast ones go through the lens or
fly on, the red soaks in."""
import os

TIMING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio", "urao_timing.json")
RIGHT, UP, LEFT, DOWN = 0, 1, 2, 3


def joins(at):
    j = []

    def soft(bar, secs=0.25):
        j.append((at(bar), "soft", secs))

    def ink(bar, secs=0.3):
        j.append((at(bar), "ink", secs))

    def rush(bar, secs=0.17):
        j.append((at(bar), "rush", secs))

    def whip(bar, direction, secs=0.17):
        j.append((at(bar), "whip", secs, direction))

    # P0: the wall from new places, then through the window into A1
    soft(5.0, 0.2)
    soft(6.0, 0.2)
    rush(7.0)
    soft(8.0, 0.33)
    # P1: slow, dissolves; the first red soaks in
    soft(10.0, 0.33)
    soft(12.0, 0.33)
    soft(14.0, 0.25)
    ink(16.0, 0.42)
    soft(20.0, 0.33)
    # P2: from the world into a picture and back, one way one bar, the other way the next
    rush(24.0, 0.12)
    for bar in (24, 25, 26, 27):
        way, back = (LEFT, RIGHT) if bar % 2 else (RIGHT, LEFT)
        if bar > 24:
            whip(bar, way, 0.12)
        whip(bar + 0.3, way, 0.12)
        whip(bar + 0.85, back, 0.12)
    rush(28.0)
    whip(29.0, LEFT)
    soft(30.0, 0.17)
    soft(31.0, 0.25)
    # P4: a camera a bar, a picture late in each (animatic_v5.p4_chorus)
    rush(35.0)
    for bar in range(36, 47):
        if bar % 3:
            whip(bar, RIGHT if bar % 2 else DOWN, 0.08)
        else:
            rush(bar, 0.08)
    for bar in range(35, 47):
        rush(bar + (0.5 if bar % 2 else 0.75), 0.08)
        if not bar % 2:
            rush(bar + 0.875, 0.04)
    # P5: the red rises and spills; black on a beat, the rain comes up out of it
    ink(47.0)
    soft(47.0 + 0.55 * 4.0, 0.25)
    ink(51.0)
    rush(55.0)
    soft(57.0, 0.33)
    # P6: slow, the rain's
    soft(59.0, 0.33)
    soft(61.0, 0.33)
    soft(62.5, 0.33)
    soft(64.0, 0.33)
    whip(66.0, DOWN, 0.12)
    # P7: 裏, slow
    soft(68.0, 0.25)
    ink(70.0, 0.42)
    for bar in (72.0, 73.0, 75.0, 76.0, 77.0, 78.0, 82.0):
        soft(bar, 0.33)
    # P8: a cut each half bar, flying from one shard to the next
    rush(83.0)
    for k in range(1, 8):
        whip(83.0 + 0.5 * k, k % 4, 0.08)
    # P9, P10
    rush(87.0)
    rush(93.0)
    ink(97.0)
    soft(98.0, 0.17)
    rush(99.0)
    rush(103.0)
    rush(107.0)
    for k in range(1, 8):
        rush(107.0 + 0.5 * k, 0.08)
    for k in range(0, 16):
        rush(111.0 + 0.25 * k, 0.04)
    rush(115.0, 0.08)
    soft(115.25, 0.17)
    soft(116.0, 0.33)
    return j
