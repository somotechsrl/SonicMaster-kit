"""Geometry shared by the performance host and its two embedded applications."""
import json,re


def load_geometry(path):
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, dict):return None
        if any(type(data.get(key)) is not int for key in ('x', 'y', 'width', 'height')):return None
        if data['width'] < 848 or data['height'] < 600:return None
        return {key: data[key] for key in ('x', 'y', 'width', 'height')}
    except (OSError, ValueError):
        return None


def save_geometry(path, geometry):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(geometry) + '\n')
    temporary.replace(path)


def fit_geometry(geometry, areas, fallback):
    """Keep the saved window on its monitor, or use the current one if removed."""
    x, y, width, height = (geometry[key] for key in ('x', 'y', 'width', 'height'))
    def overlap(area):
        ax, ay, aw, ah = area
        return max(0, min(x + width, ax + aw) - max(x, ax)) * max(0, min(y + height, ay + ah) - max(y, ay))
    area = max(areas, key=overlap, default=fallback)
    if not overlap(area):area = fallback
    ax, ay, aw, ah = area
    width = max(848, min(width, aw));height = max(600, min(height, ah))
    x = max(ax, min(x, ax + aw - width));y = max(ay, min(y, ay + ah - height))
    return dict(geometry, x=x, y=y, width=width, height=height)


def minimum_size(hints, default=(848, 187)):
    match = re.search(r'minimum size:\s*(\d+) by (\d+)', hints)
    return tuple(map(int, match.groups())) if match else default


def sizes(width, height, looper_height=187):
    # wxGTK's minimum differs between distributions. Never allocate less than
    # the application's own minimum: Openbox otherwise grows it below the host.
    bottom = max(160, looper_height)
    top = max(1, height - bottom)
    return (0, top, width, bottom), (0, 0, width, top)
