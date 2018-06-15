import math
import numpy as np
from pyrr import Vector3, Matrix44

EPSILON = 0.00001
DEFAULT_Z_NEAR = 0.01
DEFAULT_Z_FAR = 1000.0


def get_eulers(matrix):
    """
    Extracts XYZ Euler angles from a rotation matrix

    :param matrix: rotation matrix
    :type matrix: pyrr.Matrix44
    :return: XYZ Euler angles
    :rtype: pyrr.Vector3
    """
    yaw = math.asin(matrix.m13)

    if matrix.m33 < 0:
        yaw = math.pi - yaw if yaw >= 0 else -math.pi - yaw

    if EPSILON > matrix.m11 > -EPSILON:
        roll = 0.0
        pitch = math.atan2(matrix.m21, matrix.m22)
    else:
        roll = math.atan2(-matrix.m12, matrix.m11)
        pitch = math.atan2(-matrix.m23, matrix.m33)

    return Vector3([pitch, yaw, roll])


def matrix_from_xyz_eulers(angles):
    """
    Creates a rotation matrix from XYZ Euler angles

    :param angles: XYZ Euler angles
    :type angles: pyrr.Vector3
    :return: rotation matrix
    :rtype: pyrr.Matrix44
    """
    x = angles[0]
    y = angles[1]
    z = angles[2]

    sx = math.sin(x)
    cx = math.cos(x)
    sy = math.sin(y)
    cy = math.cos(y)
    sz = math.sin(z)
    cz = math.cos(z)

    return Matrix44(np.array(
        [
            # m1
            [
                cy * cz,
                -cy * sz,
                sy,
            ],
            # m2
            [
                cz * sx * sy + cx * sz,
                cx * cz - sx * sy * sz,
                -cy * sx,
            ],
            # m3
            [
                -cx * cz * sy + sx * sz,
                cz * sx + cx * sy * sz,
                cx * cy,
            ]
        ]
    ))


class Camera:
    def __init__(self, aspect, fov):
        """
        Represents a camera with pan, rotate and zoom capabilities

        :param aspect: ratio of the x and y dimension ie x / y
        :type aspect: float
        :param fov: field of view for y dimension in degrees
        :type fov: float
        """
        self.z_near = DEFAULT_Z_NEAR
        self.z_far = DEFAULT_Z_FAR
        self.moving_z_plane = self.z_near
        self.aspect = aspect
        self.fov = fov

        self.position = Vector3()
        self.target = Vector3()
        self.rot_matrix = Matrix44.identity()
        self.angle = Vector3()
        self.distance = 0.0

        self.model_view = Matrix44.identity()

    def zoomToFit(self, center, radius):
        """
        Computes the model view matrix so that camera is looking at an
        object.

        :param center: center of the object to look at
        :type center: pyrr.Vector3
        :param radius: radius of object to look at
        :type radius: float
        """
        self.inital_target = center
        self.initial_radius = radius

        direction = Vector3([0.0, 0.0, -1.0])
        half_min_fov_in_radians = 0.5 * (self.fov * math.pi / 180)

        if self.aspect < 1.0:
            # fov in x is smaller
            half_min_fov_in_radians = math.atan(
                self.aspect * math.tan(half_min_fov_in_radians))

        distance_to_center = radius / math.sin(half_min_fov_in_radians)
        eye = center - direction * distance_to_center

        self.lookAt(eye, center, Vector3([0.0, 1.0, 0.0]))

        self.z_near = distance_to_center - radius
        self.z_far = distance_to_center + radius
        self.moving_z_plane = self.z_near

    def lookAt(self, position, target, up_dir=None):
        """
        Computes the model view matrix so that camera is looking at a target
        from a desired position and orientation.

        :param position: position of camera
        :type position: pyrr.Vector3
        :param target: point to look at
        :type target: pyrr.Vector3
        :param up_dir: up direction of camera
        :type up_dir: pyrr.Vector3
        """
        self.position = position
        self.target = target
        self.model_view = Matrix44.identity()

        if position == target:
            self.model_view.from_translation(-position)
            self.rot_matrix = Matrix44.identity()
            self.angle = Vector3()
            return

        up = up_dir

        forward = position - target
        self.distance = forward.length

        forward.normalize()

        if up is None:
            condition = math.fabs(forward.x) < EPSILON and math.fabs(forward.z) < EPSILON
            if condition:
                up = Vector3([0, 0, -1]) if forward.y > 0 else Vector3([0, 0, 1])
            else:
                up = Vector3([0, 1, 0])

        left = up ^ forward  # cross product
        left.normalize()

        up = forward ^ left

        self.rot_matrix.r1[:3] = left
        self.rot_matrix.r2[:3] = up
        self.rot_matrix.r3[:3] = forward

        self.model_view.r1[:3] = left
        self.model_view.r2[:3] = up
        self.model_view.r3[:3] = forward
        
        trans = self.model_view * -position
        self.model_view.c4[:3] = trans

        self.angle = get_eulers(self.rot_matrix) * 180/math.pi

    def pan(self, delta):
        """
        Tilts the camera viewing axis vertically and/or horizontally
        while maintaining the camera position

        :param delta: offset by which camera is panned in x and y axis
        :type delta: pyrr.Vector3
        """
        # delta is scaled by distance so pan is larger when object is farther
        distance = self.distance if self.distance >= 1.0 else 1
        offset = delta * distance

        camera_left = Vector3([self.model_view.m11, self.model_view.m12, self.model_view.m13])
        camera_up = Vector3([self.model_view.m21, self.model_view.m22, self.model_view.m23])

        actual_movement = offset.x * camera_left
        actual_movement += -offset.y * camera_up  # reverse up direction

        new_target = self.target + actual_movement

        self.target = new_target
        self.computeModelViewMatrix()

    def rotate(self, delta):
        """
        Rotates the camera around the target

        :param delta: offset by which camera is rotated in each axis
        :type delta: pyrr.Vector3
        """
        self.angle = self.angle + delta
        self.rot_matrix = matrix_from_xyz_eulers(self.angle * math.pi / 180)
        self.computeModelViewMatrix()

    def zoom(self, delta):
        """
        Moves the camera forward or back along the viewing axis and adjusts
        the view frustum (z near and far) to avoid clipping.

        :param delta: offset by which camera is zoomed
        :type delta: float
        """
        # delta is scaled by distance so zoom is faster when object is farther
        distance = self.distance if self.distance >= 1.0 else 1
        offset = delta * distance

        # re-calculate view frustum
        z_depth = self.z_far - self.z_near
        self.moving_z_plane -= offset
        self.z_near = DEFAULT_Z_NEAR if self.moving_z_plane < DEFAULT_Z_NEAR else self.moving_z_plane
        self.z_far = self.z_near + z_depth

        # re-calculate camera distance
        distance -= offset
        self.distance = distance
        self.computeModelViewMatrix()

    def computeModelViewMatrix(self):
        """
        Computes the model view matrix of camera
        """
        target = self.target
        dist = self.distance
        rot = self.rot_matrix

        left = Vector3([rot.m11, rot.m21, rot.m31])
        up = Vector3([rot.m12, rot.m22, rot.m32])
        forward = Vector3([rot.m13, rot.m23, rot.m33])

        trans = Vector3()
        trans.x = left.x * -target.x + up.x * -target.y + forward.x * -target.z
        trans.y = left.y * -target.x + up.y * -target.y + forward.y * -target.z
        trans.z = left.z * -target.x + up.z * -target.y + forward.z * -target.z - dist

        self.model_view = Matrix44.identity()
        self.model_view.c1[:3] = left
        self.model_view.c2[:3] = up
        self.model_view.c3[:3] = forward
        self.model_view.c4[:3] = trans

        forward = Vector3([-self.model_view.m31, -self.model_view.m32, -self.model_view.m33])
        self.position = target - (dist * forward)

    @property
    def perspective(self):
        """
        Computes the one-point perspective projection matrix of camera

        :return: 4 x 4 perspective projection matrix
        :rtype: pyrr.Matrix44
        """
        projection = Matrix44()

        y_max = self.z_near * math.tan(0.5 * self.fov * math.pi / 180)
        x_max = y_max * self.aspect

        z_depth = self.z_far - self.z_near

        projection.m11 = self.z_near / x_max
        projection.m22 = self.z_near / y_max
        projection.m33 = (-self.z_near - self.z_far) / z_depth
        projection.m43 = -1
        projection.m34 = -2 * self.z_near * self.z_far / z_depth

        return projection

    def reset(self):
        """
        Resets the camera view
        """
        try:
            self.zoomToFit(self.inital_target, self.initial_radius)
        except AttributeError:
            self.position = Vector3()
            self.target = Vector3()

            self.rot_matrix = Matrix44.identity()
            self.angle = Vector3()
            self.distance = 0.0

            self.model_view = Matrix44.identity()

