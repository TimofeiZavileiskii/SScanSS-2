import numpy as np

eps = 0.000001


def closest_triangle_to_point(faces, points):
    """ Computes the closest face to a given 3D point. Assumes face is triangular.
    Based on code from http://www.iquilezles.org/www/articles/triangledistance/triangledistance.htm

    :param faces: faces: N x 9 array of triangular face vertices
    :type faces: numpy.ndarray
    :param points: M x 3 array of points to find closest faces
    :type points: numpy.ndarray
    :return: M x 9 array of faces corresponding to points
    :rtype: numpy.ndarray
    """
    result = []

    v1 = faces[:, 0:3]
    v2 = faces[:, 3:6]
    v3 = faces[:, 6:9]
    v21 = v2 - v1
    v32 = v3 - v2
    v13 = v1 - v3
    nor = np.cross(v21, v13)
    c13 = np.cross(v13, nor)
    c32 = np.cross(v32, nor)
    c21 = np.cross(v21, nor)
    dot_v21 = 1.0 / np.einsum('ij,ij->i', v21, v21)
    dot_v32 = 1.0 / np.einsum('ij,ij->i', v32, v32)
    dot_v13 = 1.0 / np.einsum('ij,ij->i', v13, v13)
    dot_nor = 1.0 / np.einsum('ij,ij->i', nor, nor)

    for point in points:
        dist = np.zeros(v1.shape[0], v1.dtype)

        p1 = point - v1
        p2 = point - v2
        p3 = point - v3

        mask = (np.sign(np.einsum('ij,ij->i', c21, p1)) +
                np.sign(np.einsum('ij,ij->i', c32, p2)) +
                np.sign(np.einsum('ij,ij->i', c13, p3)))

        mask = mask < 2.0

        oo = v21[mask]
        ooo = p1[mask]
        temp = oo * np.clip(np.einsum('ij,ij->i', oo, ooo) * dot_v21[mask], 0.0, 1.0)[:, np.newaxis] - ooo
        temp = np.einsum('ij,ij->i', temp, temp)

        oo = v32[mask]
        ooo = p2[mask]
        temp_2 = oo * np.clip(np.einsum('ij,ij->i', oo, ooo) * dot_v32[mask], 0.0, 1.0)[:, np.newaxis] - ooo
        temp_2 = np.einsum('ij,ij->i', temp_2, temp_2)

        oo = v13[mask]
        ooo = p3[mask]
        temp_3 = oo * np.clip(np.einsum('ij,ij->i', oo, ooo) * dot_v13[mask], 0.0, 1.0)[:, np.newaxis] - ooo
        temp_3 = np.einsum('ij,ij->i', temp_3, temp_3)

        inv_mask = ~mask
        temp_4 = np.einsum('ij,ij->i', nor[inv_mask], p1[inv_mask])
        dist[inv_mask] = temp_4 * temp_4 * dot_nor[inv_mask]

        dist[mask] = np.minimum(temp, np.minimum(temp_2, temp_3))

        closest_face = faces[dist.argmin()]
        result.append(closest_face)

    return np.array(result)


def mesh_plane_intersection(mesh, plane):
    """Gets the intersection between a triangular mesh and a plane. The algorithm returns
    a set of lines is points pairs where each even indexed point is the start of a line
    and the next point is the end. An empty list implies no intersection.
    Based on code from Real-Time Collision Detection (1st Edition) By Christer Ericson

    :param mesh: a triangular mesh
    :type mesh: sscanss.core.mesh.Mesh
    :param plane: a plane
    :type plane: sscanss.core.math.Plane
    :return: array of points pairs
    :rtype: list[numpy.ndarray]
    """
    # The algorithm checks if all vertices on each mesh face are on the same side of the plane
    # if this is true, the face does not intersect the plane. Once the faces that intersect
    # the plane are determined, the segments that form the face are tested for intersection with the plane.
    segments = []
    all_vertices = mesh.vertices[mesh.indices]
    all_dist = np.dot(all_vertices - plane.point, plane.normal)
    offsets = range(0, all_vertices.shape[0], 3)
    gg = np.logical_and.reduceat(all_dist > 0, offsets)
    ll = np.logical_and.reduceat(all_dist < 0, offsets)
    indices = np.where(~ll & ~gg)[0] * 3
    if indices.size == 0:
        return segments

    for index in indices:
        dist = all_dist[index:index + 3]
        vertices = all_vertices[index:index + 3, :]

        points = []
        nonzeros = np.nonzero(dist)[0]
        if nonzeros.size == 0:
            # all vertices on the plane we currently don't
            # care about this condition
            continue
        elif nonzeros.size == 1:
            # edge lies on the plane
            tmp = np.delete((0, 1, 2), nonzeros[0])
            a = vertices[tmp[0], :]
            b = vertices[tmp[1], :]
            segments.extend([a, b])
            continue
        elif nonzeros.size == 2:
            # point lies on plane so check intersection for a single line
            tmp = np.delete((0, 1, 2), nonzeros)
            points.append(vertices[tmp[0], :])
            face_indices = [(nonzeros[0], nonzeros[1])]
        else:
            face_indices = [(0, 1), (1, 2), (0, 2)]

        for i, j in face_indices:
            a = vertices[i, :]
            b = vertices[j, :]

            point = segment_plane_intersection(a, b, plane)
            if point is not None:
                points.append(point)

            if len(points) == 2:
                segments.extend([points[0], points[1]])
                break

    return segments


def segment_plane_intersection(point_a, point_b, plane):
    """Gets the intersection between a line segment and a plane

    :param point_a:  3D starting point of the segment
    :type point_a:numpy.ndarray
    :param point_b: 3D ending point of the segment
    :type point_b: numpy.ndarray
    :param plane: the plane
    :type plane: sscanss.core.math.Plane
    :return: point of intersection or None if no intersection
    :rtype: Union[numpy.ndarray, NoneType]
    """
    ab = point_b - point_a
    n = - np.dot(plane.normal, point_a - plane.point)
    d = np.dot(plane.normal, ab)
    if -eps < d < eps:
        # ignore case where line lies on plane
        return None
    t = n / d
    if 0.0 <= t <= 1.0:
        q = point_a + t * ab
        return q

    return None
