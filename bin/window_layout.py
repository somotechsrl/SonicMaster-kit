"""Geometry shared by the performance host and its two embedded applications."""
import re


def minimum_size(hints, default=(848, 187)):
    match = re.search(r'minimum size:\s*(\d+) by (\d+)', hints)
    return tuple(map(int, match.groups())) if match else default


def sizes(width, height, looper_height=187):
    # wxGTK's minimum differs between distributions. Never allocate less than
    # the application's own minimum: Openbox otherwise grows it below the host.
    bottom = max(160, looper_height)
    top = max(1, height - bottom)
    return (0, top, width, bottom), (0, 0, width, top)
