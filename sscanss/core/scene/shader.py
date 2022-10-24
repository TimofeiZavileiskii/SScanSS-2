import ctypes
from contextlib import suppress
import numpy as np
from OpenGL import GL, error
from OpenGL.GL import shaders

DEFAULT_VERTEX_SHADER = """
#version 120
attribute vec4 position;
varying vec4 colour;

void main(void)
{	
  colour = gl_Color;
  gl_Position = gl_ModelViewProjectionMatrix * position;
}
"""

DEFAULT_FRAGMENT_SHADER = """
#version 120

varying vec4 colour;
void main (void)
{
  gl_FragColor = colour;			
}
"""

GOURAUD_VERTEX_SHADER = """
#version 120

#define NUM_LIGHTS {0}
attribute vec4 position;
attribute vec3 vnormal;

/*******************************************************
*  Fixed.vert Fixed Function Equivalent Vertex Shader  *
*        Automatically Generated by GLSL ShaderGen     *
*          https://github.com/mojocorp/ShaderGen       *
*******************************************************/

vec4 Ambient;
vec4 Diffuse;
vec4 Specular;

void directionalLight(in int i, in vec3 normal)
{{
   float nDotVP;         // normal . light direction
   float nDotHV;         // normal . light half vector
   float pf;             // power factor

   nDotVP = max(0.0, dot(normal, normalize(vec3 (gl_LightSource[i].position))));
   nDotHV = max(0.0, dot(normal, vec3 (gl_LightSource[i].halfVector)));

   if (nDotVP == 0.0)
   {{
       pf = 0.0;
   }}
   else
   {{
       pf = pow(nDotHV, gl_FrontMaterial.shininess);
   }}

   Ambient  += gl_LightSource[i].ambient;
   Diffuse  += gl_LightSource[i].diffuse * nDotVP;
   Specular += gl_LightSource[i].specular * pf;
}}


void flight(in vec3 normal, in vec4 ecPosition, float alphaFade)
{{
    vec4 color;
    vec3 ecPosition3;
    vec3 eye;

    ecPosition3 = vec3(ecPosition) / ecPosition.w;
    eye = vec3 (0.0, 0.0, 1.0);

    // Clear the light intensity accumulators
    Ambient  = vec4 (0.0);
    Diffuse  = vec4 (0.0);
    Specular = vec4 (0.0);

    for (int i=0; i < NUM_LIGHTS; i++)
        directionalLight(i, normal);

    color = gl_FrontLightModelProduct.sceneColor +
            Ambient * gl_Color +
            Diffuse * gl_Color;

    // color += Specular * gl_FrontMaterial.specular;
    color = clamp( color, 0.0, 1.0 );

    gl_FrontColor = color;
    gl_FrontColor.a *= alphaFade;
}}


void main (void)
{{
    float alphaFade = 1.0;

    // Do fixed functionality vertex transform
    gl_Position = gl_ModelViewProjectionMatrix * position; 

    // Eye-coordinate position of vertex, needed in various calculations
    vec4 ecPosition = gl_ModelViewMatrix * position;

    vec3  transformedNormal = normalize(gl_NormalMatrix * vnormal);
    flight(transformedNormal, ecPosition, alphaFade);
}}
"""

GOURAUD_FRAGMENT_SHADER = """
#version 120
/*******************************************************
* Fixed.frag Fixed Function Equivalent Fragment Shader *
*        Automatically Generated by GLSL ShaderGen     *
*          https://github.com/mojocorp/ShaderGen       *
*******************************************************/

void main (void) 
{
    vec4 color = gl_Color;
    gl_FragColor = color;		
}
"""

VOLUME_VERTEX_SHADER = """
#version 120

attribute vec4 position;

void main(void) {
    gl_Position = gl_ModelViewProjectionMatrix * position;
    gl_FrontColor = gl_Color;
}
"""

VOLUME_FRAGMENT_SHADER = """
#version 120

uniform mat4 inverse_view_proj;
uniform bool highlight;
uniform float focal_length;
uniform float aspect_ratio;
uniform vec2 viewport_size;
uniform vec3 top;
uniform vec3 bottom;
uniform float step_length;

uniform sampler3D volume;
uniform sampler1D transfer_func;

uniform float gamma;

// Ray
struct Ray {
    vec3 origin;
    vec3 direction;
};

// Axis-aligned bounding box
struct AABB {
    vec3 top;
    vec3 bottom;
};

// Slab method for ray-box intersection
void ray_box_intersection(Ray ray, AABB box, out float t_0, out float t_1)
{
    vec3 direction_inv = 1.0 / ray.direction;
    vec3 t_top = direction_inv * (box.top - ray.origin);
    vec3 t_bottom = direction_inv * (box.bottom - ray.origin);
    vec3 t_min = min(t_top, t_bottom);
    vec2 t = max(t_min.xx, t_min.yz);
    t_0 = max(0.0, max(t.x, t.y));
    vec3 t_max = max(t_top, t_bottom);
    t = min(t_max.xx, t_max.yz);
    t_1 = min(t.x, t.y);
}

void main(void)
{
    vec4 ndc = vec4(0, 0, -1, 1);
    ndc.xy = 2.0 * gl_FragCoord.xy / viewport_size - 1.0;

    // Convert NDC through inverse clip coordinates to view coordinates
    vec4 clip = inverse_view_proj * ndc;
    vec3 vertex1 = (clip / clip.w).xyz;

    ndc.z = 1.0;
    clip = inverse_view_proj * ndc;
    vec3 vertex2 = (clip / clip.w).xyz;
    
    vec3 ray_direction = normalize(vertex2 - vertex1);
    vec3 ray_origin = vertex1; 

    float t_0, t_1;
    Ray casting_ray = Ray(ray_origin, ray_direction);
    AABB bounding_box = AABB(top, bottom);
    ray_box_intersection(casting_ray, bounding_box, t_0, t_1);

    vec3 ray_start = (ray_origin + ray_direction * t_0 - bottom) / (top - bottom);
    vec3 ray_stop = (ray_origin + ray_direction * t_1 - bottom) / (top - bottom);
    vec3 ray = ray_stop - ray_start;

    float ray_length = length(ray);
    vec3 step_vector = step_length * ray / ray_length;
    int num_of_steps = int(ceil(ray_length / step_length));

    ray_start += step_vector;
    vec3 position = ray_start;
    vec4 colour = vec4(0.0);

    if (num_of_steps > 10000)
    {
        num_of_steps = 10000;
        step_vector = ray / num_of_steps;
    }

    // Ray march until reaching the end of the volume, or colour saturation
    for (int i = 0; i < num_of_steps; i++)
    {  
        float intensity = texture3D(volume, position).r;
        vec4 c = texture1D(transfer_func, intensity);
        if (highlight)
            c = vec4(gl_Color.rgb, c.a) * intensity;

        // Alpha-blending
        colour.rgb += (1.0 - colour.a) * c.a * c.rgb;
        colour.a += (1.0 - colour.a) * c.a;

        position += step_vector;

        if (colour.a > .97)
        {
            colour.a = 1.0;
            break;
        }
    }

    // Gamma correction
    colour.rgb = pow(colour.rgb, vec3(1.0 / gamma));
    if (colour.a == 0.0f)
        discard;

    gl_FragColor = colour;
}
"""

TEXT_VERTEX_SHADER = """
#version 120
attribute vec3 vertex_pos;
attribute vec2 vertex_uv;
uniform vec2 viewport_size;
uniform vec3 screen_pos;
varying vec2 UV;

void main(void)
{
    UV = vertex_uv;
    float x = ((screen_pos.x + vertex_pos.x) * 2.0 / viewport_size.x) - 1.0;
    float y = ((screen_pos.y + vertex_pos.y) * -2.0 / viewport_size.y) + 1.0;
    float z =  2.0 * screen_pos.z - 1.0;
    gl_Position = vec4(x, y, z, 1.0);
}
"""

TEXT_FRAGMENT_SHADER = """
#version 120

varying vec2 UV;
uniform sampler2D text;

void main(void){
    gl_FragColor = texture2D(text, UV);
}
"""


class Shader:
    """Base class for a GLSL program

    :param vertex_shader: source code for vertex shaders
    :type vertex_shader: str
    :param fragment_shader: source code for fragment shaders
    :type fragment_shader: str
    """
    def __init__(self, vertex_shader, fragment_shader):
        self.id = shaders.compileProgram(shaders.compileShader(vertex_shader, GL.GL_VERTEX_SHADER),
                                         shaders.compileShader(fragment_shader, GL.GL_FRAGMENT_SHADER),
                                         validate=False)

    def destroy(self):
        """Deletes the shader program"""
        GL.glDeleteProgram(self.id)

    def bind(self):
        """Sets program associated with this object as active program in the
        current OpenGL context"""
        GL.glUseProgram(self.id)

    def setUniform(self, name, value, transpose=False):
        transpose = GL.GL_TRUE if transpose else GL.GL_FALSE
        if isinstance(value, (int, bool)):
            GL.glUniform1i(GL.glGetUniformLocation(self.id, name), value)
        elif isinstance(value, float):
            GL.glUniform1f(GL.glGetUniformLocation(self.id, name), value)
        elif np.shape(value) == (2, ):
            GL.glUniform2fv(GL.glGetUniformLocation(self.id, name), 1, value)
        elif np.shape(value) == (3, ):
            GL.glUniform3fv(GL.glGetUniformLocation(self.id, name), 1, value)
        elif np.shape(value) == (3, 3):
            GL.glUniformMatrix3fv(GL.glGetUniformLocation(self.id, name), 1, transpose, value)
        elif np.shape(value) == (4, 4):
            GL.glUniformMatrix4fv(GL.glGetUniformLocation(self.id, name), 1, transpose, value)

    def release(self):
        """Releases the active shader program in the current OpenGL context"""
        GL.glUseProgram(0)


class DefaultShader(Shader):
    """Creates a GLSL program the renders primitives with colour"""
    def __init__(self):
        super().__init__(DEFAULT_VERTEX_SHADER, DEFAULT_FRAGMENT_SHADER)


class GouraudShader(Shader):
    """Creates a GLSL program the renders primitive with Gouraud shading

    :param number_of_lights: number of lights in the scene
    :type number_of_lights: int
    """
    def __init__(self, number_of_lights):
        vertex_shader = GOURAUD_VERTEX_SHADER.format(number_of_lights)

        super().__init__(vertex_shader, GOURAUD_FRAGMENT_SHADER)


class VolumeShader(Shader):
    """Creates a GLSL program the renders a volume"""
    def __init__(self):
        super().__init__(VOLUME_VERTEX_SHADER, VOLUME_FRAGMENT_SHADER)


class TextShader(Shader):
    """Creates a GLSL program the renders a volume"""
    def __init__(self):
        super().__init__(TEXT_VERTEX_SHADER, TEXT_FRAGMENT_SHADER)


class VertexArray:
    """Creates buffers for vertex, normal, uv, and element attribute data

    :param vertices: N x 3 array of vertices
    :type vertices: numpy.ndarray
    :param indices: M x 1 array of vertices
    :type indices: numpy.ndarray
    :param normals: N x 3 array of normal
    :type normals: numpy.ndarray
    """
    def __init__(self, vertices, indices, normals=None, uvs=None):

        self.count = len(indices)
        self.buffers = []
        self.normal_buffer = None
        self.uv_buffer = None

        self.vertex_buffer = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vertex_buffer)
        GL.glBufferData(GL.GL_ARRAY_BUFFER, vertices.nbytes, vertices, GL.GL_STATIC_DRAW)
        self.buffers.append(self.vertex_buffer)

        if normals is not None and len(normals) > 0:
            self.normal_buffer = GL.glGenBuffers(1)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.normal_buffer)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, normals.nbytes, normals, GL.GL_STATIC_DRAW)
            self.buffers.append(self.normal_buffer)

        if uvs is not None and len(uvs) > 0:
            self.uv_buffer = GL.glGenBuffers(1)
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.uv_buffer)
            GL.glBufferData(GL.GL_ARRAY_BUFFER, uvs.nbytes, uvs, GL.GL_STATIC_DRAW)
            self.buffers.append(self.uv_buffer)

        self.element_buffer = GL.glGenBuffers(1)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self.element_buffer)
        GL.glBufferData(GL.GL_ELEMENT_ARRAY_BUFFER, indices.nbytes, indices, GL.GL_STATIC_DRAW)
        self.buffers.append(self.element_buffer)

        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, 0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)

    def __del__(self):
        with suppress(error.Error, ctypes.ArgumentError):
            GL.glDeleteBuffers(len(self.buffers), self.buffers)

    def bind(self):
        """Binds the buffers associated with this object to the current OpenGL context"""
        GL.glEnableVertexAttribArray(0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.vertex_buffer)
        GL.glVertexAttribPointer(0, 3, GL.GL_FLOAT, GL.GL_FALSE, 12, ctypes.c_void_p(0))

        if self.normal_buffer is not None:
            GL.glEnableVertexAttribArray(self.buffers.index(self.normal_buffer))
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.normal_buffer)
            GL.glVertexAttribPointer(1, 3, GL.GL_FLOAT, GL.GL_FALSE, 12, ctypes.c_void_p(0))

        if self.uv_buffer is not None:
            GL.glEnableVertexAttribArray(self.buffers.index(self.uv_buffer))
            GL.glBindBuffer(GL.GL_ARRAY_BUFFER, self.uv_buffer)
            GL.glVertexAttribPointer(1, 2, GL.GL_FLOAT, GL.GL_FALSE, 8, ctypes.c_void_p(0))

        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, self.element_buffer)

    def release(self):
        """Releases the buffers associated with this object from the current OpenGL context"""
        GL.glDisableVertexAttribArray(0)
        GL.glDisableVertexAttribArray(1)
        GL.glDisableVertexAttribArray(2)
        GL.glBindBuffer(GL.GL_ELEMENT_ARRAY_BUFFER, 0)
        GL.glBindBuffer(GL.GL_ARRAY_BUFFER, 0)


class Texture3D:
    """Creates buffers for 3D texture with a single channel

    :param data:  3D array of volume
    :type data: numpy.ndarray
    """
    def __init__(self, data):
        width, height, depth = data.shape

        try:
            self.pbo = GL.glGenBuffers(1)
            self.texture = GL.glGenTextures(1)
            # map and modify pixel buffer
            GL.glBindBuffer(GL.GL_PIXEL_UNPACK_BUFFER, self.pbo)
            GL.glBufferData(GL.GL_PIXEL_UNPACK_BUFFER, data.nbytes, None, GL.GL_STATIC_DRAW)
            mapped_buffer = GL.glMapBuffer(GL.GL_PIXEL_UNPACK_BUFFER, GL.GL_WRITE_ONLY)
            ctypes.memmove(mapped_buffer, data.transpose().ctypes.data, data.nbytes)
            GL.glUnmapBuffer(GL.GL_PIXEL_UNPACK_BUFFER)

            self.texture = GL.glGenTextures(1)
            GL.glBindTexture(GL.GL_TEXTURE_3D, self.texture)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_WRAP_R, GL.GL_CLAMP_TO_EDGE)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
            GL.glTexParameteri(GL.GL_TEXTURE_3D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
            GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)  # The array on the host has 1 byte alignment
            GL.glTexImage3D(GL.GL_TEXTURE_3D, 0, GL.GL_RED, width, height, depth, 0, GL.GL_RED, GL.GL_UNSIGNED_BYTE,
                            None)
        except error.Error as gl_error:
            if gl_error.err == 1285:  # out of memory error code
                raise MemoryError('Out of memory') from gl_error
            raise gl_error
        finally:
            GL.glBindTexture(GL.GL_TEXTURE_3D, GL.GL_FALSE)
            GL.glBindBuffer(GL.GL_PIXEL_UNPACK_BUFFER, GL.GL_FALSE)

    def __del__(self):
        with suppress(error.Error, ctypes.ArgumentError):
            GL.glDeleteTextures(1, [self.texture])
            GL.glDeleteBuffers(1, [self.pbo])

    def bind(self, texture=GL.GL_TEXTURE0):
        """Binds the texture to given texture unit

        :param texture: texture unit
        :type texture: GL.Constant
        """
        GL.glActiveTexture(texture)
        GL.glBindTexture(GL.GL_TEXTURE_3D, self.texture)

    def release(self):
        """Releases the buffers associated with this object from the current OpenGL context"""
        GL.glBindTexture(GL.GL_TEXTURE_3D, GL.GL_FALSE)


class Texture1D:
    """Creates buffers for 1D RGBA texture

    :param data: 1D array of RGBA values
    :type data: numpy.ndarray
    """
    def __init__(self, data):

        self.texture = GL.glGenTextures(1)

        GL.glBindTexture(GL.GL_TEXTURE_1D, self.texture)
        GL.glTexParameteri(GL.GL_TEXTURE_1D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_1D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_LINEAR)
        GL.glTexParameteri(GL.GL_TEXTURE_1D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_LINEAR)
        GL.glPixelStorei(GL.GL_UNPACK_ALIGNMENT, 1)
        GL.glTexImage1D(GL.GL_TEXTURE_1D, 0, GL.GL_RGBA, data.size // 4, 0, GL.GL_RGBA, GL.GL_FLOAT, data)
        GL.glBindTexture(GL.GL_TEXTURE_1D, GL.GL_FALSE)

    def __del__(self):
        with suppress(error.Error, ctypes.ArgumentError):
            GL.glDeleteTextures(1, [self.texture])

    def bind(self, texture=GL.GL_TEXTURE0):
        """Binds the texture to given texture unit

        :param texture: texture unit
        :type texture: GL.Constant
        """
        GL.glActiveTexture(texture)
        GL.glBindTexture(GL.GL_TEXTURE_1D, self.texture)

    def release(self):
        """Releases the texture from the current OpenGL context"""
        GL.glBindTexture(GL.GL_TEXTURE_1D, GL.GL_FALSE)


class Texture2D:
    """Creates buffers for 2D RGBA texture

    :param data: 2D array of RGBA values
    :type data: numpy.ndarray
    """
    def __init__(self, data):

        self.texture = GL.glGenTextures(1)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)

        # Set the texture wrapping parameters
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_S, GL.GL_CLAMP_TO_EDGE)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_WRAP_T, GL.GL_CLAMP_TO_EDGE)

        # Set texture filtering parameters
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MIN_FILTER, GL.GL_NEAREST)
        GL.glTexParameteri(GL.GL_TEXTURE_2D, GL.GL_TEXTURE_MAG_FILTER, GL.GL_NEAREST)

        GL.glTexImage2D(GL.GL_TEXTURE_2D, 0, GL.GL_RGBA, data.shape[1], data.shape[0], 0, GL.GL_RGBA,
                        GL.GL_UNSIGNED_BYTE, data)

    def __del__(self):
        with suppress(error.Error, ctypes.ArgumentError):
            GL.glDeleteTextures(1, [self.texture])

    def bind(self, texture=GL.GL_TEXTURE0):
        """Binds the texture to given texture unit

        :param texture: texture unit
        :type texture: GL.Constant
        """
        GL.glActiveTexture(GL.GL_TEXTURE0)
        GL.glBindTexture(GL.GL_TEXTURE_2D, self.texture)

    def release(self):
        """Releases the texture from the current OpenGL context"""
        GL.glBindTexture(GL.GL_TEXTURE_1D, GL.GL_FALSE)


class Text3D:
    """Creates buffers for text data

    :param size: font dimension i.e. width and height
    :type size: Tuple[int, int]
    :param image_data: 2d image containing text
    :type image_data: numpy.ndarray
    """
    def __init__(self, size, image_data):
        self.texture = Texture2D(image_data)

        half_width, half_height = size[0] / 2, size[1] / 2
        vertices = np.array([[-half_width, -half_height, 0], [-half_width, half_height, 0.],
                             [half_width, -half_height, 0.], [half_width, half_height, 0.]], np.float32)
        uvs = np.array([[0, 0], [0, 1], [1, 0], [1, 1]], np.float32)
        indices = np.array([0, 1, 2, 1, 2, 3], np.uint32)

        self.vertex_array = VertexArray(vertices, indices, uvs=uvs)
        self.count = self.vertex_array.count

    def __del__(self):
        with suppress(error.Error, ctypes.ArgumentError):
            del self.texture
            del self.vertex_array

    def bind(self):
        """Binds the buffers associated with this object to the current OpenGL context"""
        self.texture.bind()
        self.vertex_array.bind()

    def release(self):
        """Releases the buffers associated with this object from the current OpenGL context"""
        self.vertex_array.release()
        self.texture.release()
