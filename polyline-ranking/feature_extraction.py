import polyline
import numpy as np


def decode_polyline(polyline_str):
    """Decode a polyline into a list of (lat, lon) tuples."""
    return np.array(polyline.decode(polyline_str))


def calculate_features(polyline_str):
    """Extract features from a polyline."""
    # Decode the polyline
    points = decode_polyline(polyline_str)
    if len(points) < 2:
        return None  # Invalid polyline

    # Compute distances between consecutive points
    distances = np.linalg.norm(np.diff(points, axis=0), axis=1)
    total_length = np.sum(distances)

    # Compute angles between consecutive segments
    def compute_angles(points):
        angles = []
        for i in range(1, len(points) - 1):
            v1 = points[i] - points[i - 1]
            v2 = points[i + 1] - points[i]
            cosine_angle = np.dot(v1, v2) / \
                (np.linalg.norm(v1) * np.linalg.norm(v2))
            # Clip for numerical stability
            angle = np.arccos(np.clip(cosine_angle, -1.0, 1.0))
            angles.append(np.degrees(angle))
        return np.array(angles)

    angles = compute_angles(points)
    sharp_turns = np.sum(angles > 90)  # Count sharp turns

    # Self-intersections

    def count_intersections(points):
        from shapely.geometry import LineString, Point

        # Create a LineString from the points
        line = LineString(points)

        # Calculate the intersections of the line with itself
        intersections = line.intersection(line)

        # Count intersection points
        if intersections.is_empty:  # No intersections
            return 0
        elif isinstance(intersections, Point):  # Single intersection
            return 1
        else:  # Multiple intersections (MultiPoint, MultiLineString, etc.)
            return len(intersections.geoms)

    intersections = count_intersections(points)

    # Bounding box features
    x_min, y_min = points.min(axis=0)
    x_max, y_max = points.max(axis=0)
    bounding_box_area = (x_max - x_min) * (y_max - y_min)
    compactness = bounding_box_area / total_length if total_length != 0 else 0

    # Start-to-end distance
    start_end_distance = np.linalg.norm(points[0] - points[-1])

    # Feature dictionary
    features = {
        "total_length": total_length,
        "num_points": len(points),
        "sharp_turns": sharp_turns,
        "intersections": intersections,
        "bounding_box_area": bounding_box_area,
        "compactness": compactness,
        "start_end_distance": start_end_distance,
        "angular_variance": np.var(angles) if len(angles) > 0 else 0,
    }
    return features
