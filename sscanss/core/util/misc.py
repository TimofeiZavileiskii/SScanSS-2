from enum import Enum, unique

@unique
class Directions(Enum):
    right = '+X'
    left = '-X'
    front = '+Y'
    back = '-Y'
    up = '+Z'
    down = '-Z'


@unique
class SceneType(Enum):
    Sample = 1
    Instrument = 2


@unique
class TransformType(Enum):
    Rotate = 'Rotate'
    Translate = 'Translate'


@unique
class Primitives(Enum):
    Cuboid = 'Cuboid'
    Cylinder = 'Cylinder'
    Sphere = 'Sphere'
    Tube = 'Tube'


@unique
class CompareOperator(Enum):
    Equal = 1
    Not_Equal = 2
    Greater = 3
    Less = 4


def to_float(string):
    try:
        return float(string), True
    except ValueError:
        return None, False


def clamp(value, min_value=0.0, max_value=1.0):
    return max(min(value, max_value), min_value)
