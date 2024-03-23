# G-code parsing and visualization in Blender
# https://github.com/apetsiuk/GCode-Parser-and-Viz


import bpy
import numpy as np
import math
import random


#            PARSER
#----------------------------------------------------------------------------
class Segment:
    def __init__(self,move_type,coords,layer_index,shell,fill,support,other):
        self.type = move_type
        self.coords = coords
        self.layer_index = layer_index
        self.shell = shell
        self.fill = fill
        self.support = support
        self.other = other
        self.style = None
        
        
class Parser:

    def __init__(self):
        self.relative = {"X":0.0,"Y":0.0,"F":0.0,"E":0.0, "z_height":0.0}
        self.isRelative = False
        self.segments = []
        self.layer_number = 0
        self.z_height = 0.0
        self.layers = []
        self.shell = 0
        self.fill = 0
        self.support = 0
        self.other = 0

    def parseFile(self,path):
        with open(path, 'r') as f:
            self.lineNb = 0
            for line in f:
                self.lineNb += 1
                self.line = line.rstrip()
                self.parseLine()

    def parseLine(self):
        bits = self.line.split(';',1)
        if(len(bits)>1):
            if (bits[1][:12] == 'LAYER_CHANGE'):
                self.layer_number += 1
                #self.z_height += 0.3
                
        if(len(bits)>1):
            if (bits[1][:15] == 'LAYER_Z_HEIGHT='):
                self.z_height = float(bits[1][15:])

        if(len(bits)>1):
            if (bits[1][:20] == "TYPE:Internal infill" or
                  bits[1][:17] == "TYPE:Solid infill" or
                  bits[1][:21] == "TYPE:Top solid infill" or
                  bits[1][:18] == "TYPE:Bridge infill"):
                self.shell = 0
                self.fill = 1
                self.support = 0
                self.other = 0
            elif (bits[1][:14] == "TYPE:Perimeter" or
                bits[1][:23] == "TYPE:External perimeter" or
                bits[1][:23] == "TYPE:Overhang perimeter"):
                self.shell = 1
                self.fill = 0
                self.support = 0
                self.other = 0

            elif (bits[1][:21] == "TYPE:Support material" or
                  bits[1][:31] == "TYPE:Support material interface"):
                self.shell = 0
                self.fill = 0
                self.support = 1
                self.other = 0
            '''else:
                self.shell = 0
                self.fill = 0
                self.support = 0
                self.other = 1'''

        command = bits[0].strip()
        comm = command.split(None, 1)
        code = comm[0] if (len(comm)>0) else None # G
        args = comm[1] if (len(comm)>1) else None # XYEF

        if code:
            if hasattr(self, "parse_"+code):
                getattr(self, "parse_"+code)(args)
                #print("code= ", code, ": args= ", args)
            return code,args

    def parseArgs(self, args):
        dic = {}
        if args:
            bits = args.split()
            for bit in bits:
                letter = bit[0]
                try:
                    coord = float(bit[1:])
                except ValueError:
                    coord = 1
                dic[letter] = coord
        return dic

    def parse_G0(self, args, move_type="G0"):
        self.do_G0_G1(self.parseArgs(args), move_type)

    def parse_G1(self, args, move_type="G1"):
        self.do_G0_G1(self.parseArgs(args), move_type)

    def do_G0_G1(self,args,move_type):
        coords = dict(self.relative)
        for axis in args.keys():
            if axis in coords:
                if self.isRelative:
                    coords[axis] += args[axis]
                else:
                    coords[axis] = args[axis]
        # build segment
        absolute = {"X": coords["X"],"Y": coords["Y"],"z_height": self.z_height}
        if "E" not in args : #"E" in coords:
            absolute["E"] = 0
        else:
            absolute["E"] = args["E"]

        seg = Segment(move_type,absolute,self.layer_number,self.shell,self.fill,self.support,self.other)

        if (seg.coords['X'] != self.relative['X'] or
            seg.coords['Y'] != self.relative['Y']):
            self.segments.append(seg)
        self.relative = coords
        return self.relative

    def classifySegments(self):
        coords = {"X":0.0,"Y":0.0,"Z":0.0,"F":0.0,"E":0.0}
        current_layer = 0
        layer = []

        for i, seg in enumerate(self.segments):
            # default style is travel (move, no extrusion)
            style = "travel"

            # some horizontal movement, and positive extruder movement: extrusion
            if (((seg.coords["X"] != coords["X"])
                    or (seg.coords["Y"] != coords["Y"])
                    or (seg.coords["z_height"] != coords["Z"])) and (seg.coords["E"]>0)): #!= coords["E"]
                style = "extrude"

            if i==len(self.segments)-1:
                layer.append(seg)
                current_layer += 1
                seg.style = style
                seg.layer_index = current_layer
                self.layers.append(layer)
                print('**Segment classification complete**')
                break

            if (self.segments[i].layer_index != current_layer):
                self.layers.append(layer)
                layer = []
                current_layer+=1

            # set style and layer in segment
            seg.style = style
            coords = seg.coords
            layer.append(seg)
            
            
            
#            Load and parse a file
#----------------------------------------------------------------------------
# TODO: change the file location          
parser = Parser()
parser.parseFile('C:/.../gcode_viz_0.4n_0.3mm_PLA_MK3SMMU2S_2h19m.gcode')

parser.classifySegments()
print(len(parser.segments))
print(len(parser.layers))

print(parser.layer_number)
print(parser.z_height)


#            GCODE TO MESH IN BLENDER
#----------------------------------------------------------------------------

def segments_to_meshdata(segments): # edges only on extrusion
    segs = segments
    verts=[]
    edges=[]
    props = []
    
    del_offset=0 # to travel segs in a row, one gets deleted, need to keep track of index for edges
    for i in range(len(segs)):
        # props.append(0)
        if i>=len(segs)-1:
            if segs[i].style == 'extrude':
                verts.append([segs[i].coords['X'],segs[i].coords['Y'],segs[i].coords['z_height'] ])
            break
            
            
        # start of extrusion for first time
        if segs[i].style == 'travel' and segs[i+1].style == 'extrude':
            verts.append([segs[i].coords['X'],segs[i].coords['Y'],segs[i].coords['z_height'] ])
            verts.append([segs[i+1].coords['X'],segs[i+1].coords['Y'],segs[i+1].coords['z_height'] ])
            edges.append([i-del_offset,(i-del_offset)+1])
            
            if segs[i+1].fill == 1:
                props.append('fill')
            elif segs[i+1].shell == 1:
                props.append('shell')
            elif segs[i+1].support == 1:
                props.append('support')
            else:
                props.append('NA')
                

        # mitte, current and next are extrusion, only add next, current is already in vert list
        if segs[i].style == 'extrude' and segs[i+1].style == 'extrude':
            verts.append([segs[i+1].coords['X'],segs[i+1].coords['Y'],segs[i+1].coords['z_height'] ])
            edges.append([i-del_offset,(i-del_offset)+1])

            if segs[i+1].fill == 1:
                props.append('fill')
            elif segs[i+1].shell == 1:
                props.append('shell')
            elif segs[i+1].support == 1:
                props.append('support')
            else:
                props.append('NA')
 
        if segs[i].style == 'travel' and segs[i+1].style == 'travel':
            del_offset+=1
        
    return verts, edges, props



def obj_from_pydata(name,verts,edges,close,collection_name):
    if edges is None:
        # join vertices into one uninterrupted chain of edges.
        edges = [[i, i+1] for i in range(len(verts)-1)]
        if close:
            edges.append([len(verts)-1, 0]) # connect last to first
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, edges, [])   
    obj = bpy.data.objects.new(name, me)
   
    # Move into collection if specified
    if collection_name != None: # make argument optional
        # collection exists                   
        collection = bpy.data.collections.get(collection_name)
        if collection: 
            bpy.data.collections[collection_name].objects.link(obj)
        else:
            collection = bpy.data.collections.new(collection_name)
            bpy.context.scene.collection.children.link(collection) # link collection to main scene
            bpy.data.collections[collection_name].objects.link(obj) 
#----------------------------------------------------------------------------



#            MATERIAL DEVELOPMENT
#----------------------------------------------------------------------------
gcode_mat = bpy.data.materials.new(name = "GCode Material")
gcode_mat.use_nodes = True
nodes = gcode_mat.node_tree.nodes

material_output = nodes.get("Material Output")
material_output.location = (500,200)

# https://docs.blender.org/api/current/bpy.types.ShaderNode.html
color_RGB_1 = gcode_mat.node_tree.nodes.new('ShaderNodeRGB')
color_RGB_1.location = (-1800,700)
#color_RGB_1.outputs[0].default_value = (1,0.105,0.034,1)
color_RGB_1.outputs[0].default_value = (random.randint(1, 1000)/1000,random.randint(1, 1000)/1000,random.randint(1, 1000)/1000,1)

color_RGB_2 = gcode_mat.node_tree.nodes.new('ShaderNodeRGB')
color_RGB_2.location = (-1800,500)
#color_RGB_2.outputs[0].default_value = (1,0.626,0.0767,1)
color_RGB_2.outputs[0].default_value = (random.randint(1, 1000)/1000,random.randint(1, 1000)/1000,random.randint(1, 1000)/1000,1)

principled_node = gcode_mat.node_tree.nodes.new('ShaderNodeBsdfPrincipled')
principled_node.location = (-850,250)
texture_coords = gcode_mat.node_tree.nodes.new('ShaderNodeTexCoord')
texture_coords.location = (-2050,200)
texture_voronoi = gcode_mat.node_tree.nodes.new('ShaderNodeTexVoronoi')
texture_voronoi.location = (-1850,-50)
texture_noise = gcode_mat.node_tree.nodes.new('ShaderNodeTexNoise')
texture_noise.location = (-1850,200)
mix_rgb_1 = gcode_mat.node_tree.nodes.new('ShaderNodeMixRGB')
mix_rgb_1.location = (-1650,100)
color_ramp_1 = gcode_mat.node_tree.nodes.new('ShaderNodeValToRGB')
color_ramp_1.location = (-1450,250)
color_ramp_2 = gcode_mat.node_tree.nodes.new('ShaderNodeValToRGB')
color_ramp_2.location = (-1450,-50)
mix_rgb_2 = gcode_mat.node_tree.nodes.new('ShaderNodeMixRGB')
mix_rgb_2.location = (-1100,250)
add_node = gcode_mat.node_tree.nodes.new('ShaderNodeMath')
add_node.location = (-1100,50)
bump_node = gcode_mat.node_tree.nodes.new('ShaderNodeBump')
bump_node.location = (-1100,-200)
glossy_bsdf = gcode_mat.node_tree.nodes.new('ShaderNodeBsdfGlossy')
glossy_bsdf.location = (-550,0)
diffuse_bsdf = gcode_mat.node_tree.nodes.new('ShaderNodeBsdfDiffuse')
diffuse_bsdf.location = (-550,-200)

mixer_node_1 = gcode_mat.node_tree.nodes.new('ShaderNodeMixShader')
mixer_node_1.location = (-300,-50)
mixer_node_1.inputs[0].default_value = 0.23

transparent_bsdf = gcode_mat.node_tree.nodes.new('ShaderNodeBsdfTransparent')
transparent_bsdf.location = (-100,20)


# Node names are here: https://docs.blender.org/api/current/bpy.types.ShaderNode.html
#translucent_node = shell_mat.node_tree.nodes.new('ShaderNodeBsdfTranslucent')
#translucent_node.location = (50,0)
#translucent_node.inputs[0].default_value = (0.799,0.143,0.080,1.0)
mixer_node_2 = gcode_mat.node_tree.nodes.new('ShaderNodeMixShader')
mixer_node_2.location = (100,-70)
#mixer_node_2.inputs[0].default_value = 0.23
mixer_node_3 = gcode_mat.node_tree.nodes.new('ShaderNodeMixShader')
mixer_node_3.location = (300,100)
#shell_mat.node_tree.links.new(translucent_node.outputs[0],mixer_node_2.inputs[2])
gcode_mat.node_tree.links.new(principled_node.outputs[0],mixer_node_3.inputs[1])
gcode_mat.node_tree.links.new(mixer_node_3.outputs[0],material_output.inputs[0])


gcode_mat.node_tree.links.new(texture_coords.outputs[0],texture_noise.inputs[0])
gcode_mat.node_tree.links.new(texture_noise.outputs[1],mix_rgb_1.inputs[1])
gcode_mat.node_tree.links.new(texture_voronoi.outputs[1],mix_rgb_1.inputs[2])
gcode_mat.node_tree.links.new(mix_rgb_1.outputs[0],color_ramp_1.inputs[0])
gcode_mat.node_tree.links.new(mix_rgb_1.outputs[0],color_ramp_2.inputs[0])
gcode_mat.node_tree.links.new(color_ramp_1.outputs[0],mix_rgb_2.inputs[0])


gcode_mat.node_tree.links.new(color_RGB_1.outputs[0],mix_rgb_2.inputs[2])
gcode_mat.node_tree.links.new(color_RGB_1.outputs[0],diffuse_bsdf.inputs[0])
gcode_mat.node_tree.links.new(color_RGB_1.outputs[0],transparent_bsdf.inputs[0])

gcode_mat.node_tree.links.new(color_RGB_2.outputs[0],mix_rgb_2.inputs[1])
gcode_mat.node_tree.links.new(color_RGB_2.outputs[0],principled_node.inputs[3])
gcode_mat.node_tree.links.new(color_RGB_2.outputs[0],glossy_bsdf.inputs[0])


gcode_mat.node_tree.links.new(color_ramp_1.outputs[0],add_node.inputs[0])
gcode_mat.node_tree.links.new(add_node.outputs[0],principled_node.inputs[7])
gcode_mat.node_tree.links.new(color_ramp_2.outputs[0],bump_node.inputs[2])
gcode_mat.node_tree.links.new(bump_node.outputs[0],principled_node.inputs[22])
gcode_mat.node_tree.links.new(mix_rgb_2.outputs[0],principled_node.inputs[0])
gcode_mat.node_tree.links.new(glossy_bsdf.outputs[0],mixer_node_1.inputs[1])
gcode_mat.node_tree.links.new(diffuse_bsdf.outputs[0],mixer_node_1.inputs[2])
gcode_mat.node_tree.links.new(mixer_node_1.outputs[0],mixer_node_2.inputs[2])

gcode_mat.node_tree.links.new(transparent_bsdf.outputs[0],mixer_node_2.inputs[1])
gcode_mat.node_tree.links.new(mixer_node_2.outputs[0],mixer_node_3.inputs[2])

# https://blender.stackexchange.com/questions/189712/how-to-add-a-new-stop-to-the-color-ramp
#bpy.data.materials["Shell Material.001"].node_tree.nodes["Glossy BSDF.001"].distribution = 'BECKMANN'

texture_noise.inputs[2].default_value = 20
texture_noise.inputs[3].default_value = 8
texture_noise.inputs[4].default_value = 0.5
texture_noise.inputs[5].default_value = 2

texture_voronoi.inputs[2].default_value = 50

mix_rgb_1.inputs[0].default_value = 0.75

color_ramp_1.color_ramp.elements[0].position = (0.0)
color_ramp_1.color_ramp.elements[1].position = (1.0)

#mix_rgb_2.inputs['Color1'].default_value = (1.0,0.087,0.067,1)
#mix_rgb_2.inputs['Color2'].default_value = (0.815,0.098,0.114,1)
mix_rgb_2.inputs['Color1'].default_value = (0.568,1,1,1)
mix_rgb_2.inputs['Color2'].default_value = (1,1,1,1)

add_node.inputs[1].default_value = 0.3

bump_node.invert = True
bump_node.inputs[0].default_value = 0.75
bump_node.inputs[1].default_value = 20.0

glossy_bsdf.distribution = 'BECKMANN'
glossy_bsdf.inputs['Color'].default_value = (1,1,1,1)
glossy_bsdf.inputs[1].default_value = 0.8


diffuse_bsdf.inputs['Color'].default_value = (1,1,1,1)
diffuse_bsdf.inputs[1].default_value = 0.7
mixer_node_1.inputs[0].default_value = 0.5
mixer_node_2.inputs[0].default_value = 0.5
mixer_node_3.inputs[0].default_value = 0.7

principled_node.distribution = 'GGX'
principled_node.subsurface_method = 'BURLEY'

#principled_node.inputs[0].default_value = (0.799,0.074,0.051,1.0) # color
principled_node.inputs[1].default_value = 0.255 # subsurface
#principled_node.inputs[3].default_value = (1,1,1,1.0) # subsurface color

# 4 - Metallic
principled_node.inputs[6].default_value = 0.0
# 5 - Specular
#principled_node.inputs[7].default_value = 0.830
# 6 - Specular tint
principled_node.inputs[8].default_value = 0.0
# 7 - Roughness
principled_node.inputs[9].default_value = 0.0
# 8 - Anisotropic
principled_node.inputs[10].default_value = 0.0
## 9 - Anisotropic rotation
#principled_node.inputs[9].default_value = 0.0
## 10 - Sheen 
#principled_node.inputs[10].default_value = 0.0
## 11 - Sheen tint
principled_node.inputs[13].default_value = 0.5
# 12 - Clearcoat
principled_node.inputs[14].default_value = 0.0
# 13 - Clearcoat roughness
principled_node.inputs[15].default_value = 0.0
# 14 - IOR
principled_node.inputs[16].default_value = 1.45
# 15 - Transmission
principled_node.inputs[17].default_value = 1
## 16 - Transmission roughness
#principled_node.inputs[16].default_value = 0.0
# 17 - Emission
principled_node.inputs[19].default_value = (0.2,0.2,0.2,1.0)
# 18 -  Emission Strength
principled_node.inputs[20].default_value = 0.1
# 19 - Alpha
principled_node.inputs[21].default_value = 1
#ShaderNodeBsdfPrincipled.subsurface_method = 'BURLEY'
#----------------------------------------------------------------------------



#            COMPOSITING
#----------------------------------------------------------------------------
'''
bpy.context.scene.use_nodes = True
bpy.context.scene.node_tree.nodes.new("CompositorNodeRLayers")
bpy.context.scene.node_tree.nodes.new("CompositorNodeViewer")
bpy.context.scene.node_tree.nodes.new("CompositorNodeMath")
bpy.context.scene.node_tree.nodes.new("CompositorNodeOutputFile")
'''




#            ACTUAL PROCESSING
#----------------------------------------------------------------------------
#LN = 50
#verts, edges, props = segments_to_meshdata(parser.layers[LN])

for i in range(1,len(parser.layers)-0):
    verts, edges, props = segments_to_meshdata(parser.layers[i])
    print('-> verts and edges for L= ',i)

    if(len(edges)>0):
        obj_from_pydata('layer_'+str(i),verts,edges,True,"Layers")

# TODO: Adjust the layer height ccording to slicer parameters
LINE_HEIGHT = 0.25

def process_layers():
    if(len(bpy.data.collections['Layers'].objects)>0):
        for i in range(len(bpy.data.collections['Layers'].objects)):
            obj = bpy.data.collections['Layers'].objects[i]
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.convert(target='CURVE')
            bpy.context.object.data.bevel_depth=LINE_HEIGHT
            bpy.context.object.data.use_fill_caps=True
            bpy.ops.object.shade_smooth()
        
            so = bpy.context.active_object
            # place them at the initial invisible location
            so.location[0] = 500 # 200
            so.location[1] = 0
            so.location[2] = -100 # -100
            
            so.data.materials.append(gcode_mat)
            so.pass_index = 128
            print('-> processed L= ',i)



def camera_debug():
    s_cam = bpy.data.collections['Collection'].objects['Camera']
    s_cam.select_set(True)
    bpy.context.view_layer.objects.active = s_cam
    so = bpy.context.active_object
    
    # origin - where you place the gcode mesh
    origin_x = 120
    origin_y = 110
    origin_z = 0
    
    # set camera angles to zero
    so.rotation_euler[0] = 0
    so.rotation_euler[1] = 0
    so.rotation_euler[2] = 0
    
    so.location[0] = random.randint(10, 230)+0.1
    so.location[1] = random.randint(10, 230)+0.1
    so.location[2] = random.randint(20, 100)+0.1
    
    
    angle_x_rad = math.atan((so.location[1]-origin_y)/(so.location[2]-origin_z))
    angle_y_rad = math.atan((so.location[0]-origin_x)/(so.location[2]-origin_z))
    
    so.rotation_euler[0] = (so.rotation_euler[0]-angle_x_rad)
    so.rotation_euler[1] = (so.rotation_euler[1]+angle_y_rad)
    #print(math.degrees(angle_x_rad))
    
    print('Camera moced to ({},{},{}) m(?).'.format(so.location[0],so.location[1],so.location[2]))
    
            

def animate_layers():
    
    ind = 0
    frame_count = 0
    
    if(len(bpy.data.collections['Layers'].objects)>0):
        for i in range(len(bpy.data.collections['Layers'].objects)-0):
            ind += 1
            
            obj = bpy.data.collections['Layers'].objects[i]
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            so = bpy.context.active_object
            
            # place them at the desired location
            so.location[0] = 50
            so.location[1] = 55
            so.location[2] = 0
            so.pass_index = 255
        
            # origin - where you place the gcode mesh
            origin_x = 120
            origin_y = 110
            origin_z = 0

            so.keyframe_insert(data_path="location",frame=i+1)
            bpy.data.scenes["Scene"].frame_current = i+1
            #so.select_set(False)
            #------------------------------------
            
            # LIGHT MANIPULATION
            s_light_1 = bpy.data.collections['Collection'].objects['Light_point']
            s_light_1.select_set(True)
            bpy.context.view_layer.objects.active = s_light_1
            so = bpy.context.active_object
            # set light coordinates
            so.location[0] = random.randint(50, 230)+0.1
            so.location[1] = random.randint(1, 190)+0.1
            so.location[2] = random.randint(50, 180)+0.1
            
            s_light_2 = bpy.data.collections['Collection'].objects['Light_area']
            s_light_2.select_set(True)
            bpy.context.view_layer.objects.active = s_light_2
            so = bpy.context.active_object
            # set light coordinates
            so.location[0] = random.randint(50, 230)+0.1
            so.location[1] = random.randint(1, 190)+0.1
            so.location[2] = random.randint(50, 180)+0.1
            so.rotation_euler[2] = random.randint(0, 200)/100 # radians (?)
            
            s_light_3 = bpy.data.collections['Collection'].objects['Light_sun']
            s_light_3.select_set(True)
            bpy.context.view_layer.objects.active = s_light_3
            so = bpy.context.active_object
            # set light coordinates
            so.location[0] = random.randint(10, 350)+0.1
            so.location[1] = random.randint(1, 320)+0.1
            so.location[2] = random.randint(60, 300)+0.1
            #------------------------------------
            
            # BED MANIPULATION
            s_bed = bpy.data.collections['Collection'].objects['Bed']
            s_bed.select_set(True)
            bpy.context.view_layer.objects.active = s_bed
            so = bpy.context.active_object
            
            # set bed coordinates
            so.location[0] = random.randint(90, 150)+0.1
            so.location[1] = random.randint(80, 140)+0.1
            so.rotation_euler[2] = random.randint(0, 200)/100
            s_bed.select_set(False)
            
            
            #------------------------------------
            
            # CAMERA MANIPULATION
            s_cam = bpy.data.collections['Collection'].objects['Camera']
            s_cam.select_set(True)
            bpy.context.view_layer.objects.active = s_cam
            so = bpy.context.active_object
            
            # set camera angles to zero
            so.rotation_euler[0] = 0
            so.rotation_euler[1] = 0
            so.rotation_euler[2] = 0
    
            so.location[0] = random.randint(10, 230)+0.1
            so.location[1] = random.randint(10, 230)+0.1
            so.location[2] = i+10+random.randint(10, 30)+0.1
    
            angle_x_rad = math.atan((so.location[1]-origin_y)/(so.location[2]-origin_z))
            angle_y_rad = math.atan((so.location[0]-origin_x)/(so.location[2]-origin_z))
            so.rotation_euler[0] = (so.rotation_euler[0]-angle_x_rad)
            so.rotation_euler[1] = (so.rotation_euler[1]+angle_y_rad)
            #print(math.degrees(angle_x_rad))
            print('Camera moved to ({},{},{}) m(?).'.format(so.location[0],so.location[1],so.location[2]))
            
            bpy.context.scene.render.filepath = f"C:/.../image_L{i}.png"
            
            if(ind % 10 == 0):
                frame_count += 1
                print('frame_count=',frame_count)
                bpy.ops.render.render(write_still=True)
            
                '''
                mask_image = bpy.data.images['Viewer Node']
                mask_image.filepath = f"C:/.../mask_L{i}.png"
                mask_image.file_format = 'PNG'
                mask_image.save()
                '''
            
                print('Saved {} out of {}'.format(i,len(bpy.data.collections['Layers'].objects)-1))
            
            # Set the pass index back to the original value
            obj = bpy.data.collections['Layers'].objects[i]
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            so = bpy.context.active_object
            so.pass_index = 128
    

def del_collection(coll):
    for c in coll.children:
        del_collection(c)
    bpy.data.collections.remove(coll,do_unlink=True)
    
    
# ---- BED Texture ----
bed_textire_list = []
for filename in glob.glob('C:/.../GCODE_VIZ_BLENDER/_FOR_TRAINING/_beds/*.*'):
    bed_textire_list.append(filename)
    
# ---- HDRI Texture ----
hdri_textire_list = []
for filename in glob.glob('C:/.../GCODE_VIZ_BLENDER/_FOR_TRAINING/_environments/*.exr'):
    hdri_textire_list.append(filename)


#--------------------------------------------------
keyframe_runner = 1
for i in range(len(bed_textire_list)): # BED Texture
    bpy.ops.import_image.to_plane(shader='SHADELESS', files=[{'name':bed_textire_list[i]}])
    bed_name = {'name':bed_textire_list[i]}["name"]
    print('BED_NAME=',bed_name)
    # whole file path - ".jpg"
    bed_name = bed_name[len('C:/.../GCODE_VIZ_BLENDER/_FOR_TRAINING/_beds/'):-4]

    #s_bed = bpy.data.collections['Collection'].objects[str(bed_name)]
    s_bed = bpy.data.objects[str(bed_name)]
    s_bed.select_set(True)
    bpy.context.view_layer.objects.active = s_bed
    so = bpy.context.active_object
    # set coordinates and scale
    so.location[0] = random.randint(90, 150)+0.1
    so.location[1] = random.randint(80, 140)+0.1
    so.location[2] = 0
    
    #so.location[2] = -600
    #so.location[2] = -600
    #so.location[2] = -600
    
    so.rotation_euler[0] = 0 # radians (?)
    so.rotation_euler[2] = random.randint(0, 200)/100
    #so.scale = (190,190,190)
    so.scale = (250,250,250)
    s_bed.select_set(False)
    
        
    for j in range(len(hdri_textire_list)): # HDRI Env.
        keyframe_runner += 1
        C = bpy.context
        scn = C.scene
        # Get the environment node tree of the current scene
        node_tree = scn.world.node_tree
        tree_nodes = node_tree.nodes
        # Clear all nodes
        tree_nodes.clear()
        # Add Background node
        node_background = tree_nodes.new(type='ShaderNodeBackground')
        # Add Environment Texture node
        node_environment = tree_nodes.new('ShaderNodeTexEnvironment')
        # Load and assign the image to the node property
        node_environment.image = bpy.data.images.load(hdri_textire_list[j]) # Relative path
        node_environment.location = -300,0
        # Add Output node
        node_output = tree_nodes.new(type='ShaderNodeOutputWorld')   
        node_output.location = 200,0
        # Link all nodes
        links = node_tree.links
        link = links.new(node_environment.outputs["Color"], node_background.inputs["Color"])
        link = links.new(node_background.outputs["Background"], node_output.inputs["Surface"])
        
        #---------------- ANIMATION ----------------
        for m in range(1,len(parser.layers)-232):
            verts, edges, props = segments_to_meshdata(parser.layers[m])
            print('-> verts and edges for L= ',m)
            if(len(edges)>0):
                obj_from_pydata('layer_'+str(m),verts,edges,True,"Layers")
    
        LINE_HEIGHT = 0.26
        process_layers()
        animate_layers(keyframe_runner*48) # 333/25 = 13.32
        #-----------------------------------------
        
        # delete all the layers (with keyframes) after rendering
        del_collection(bpy.data.collections["Layers"])
        # end of j (HDRI Env.)
        

    sacrificial_cube = bpy.data.collections['Collection'].objects['Cube']
    sacrificial_cube.select_set(False)
    # delete bed texture
    bpy.data.objects[str(bed_name)].select_set(True) # Blender 2.8x
    # MAKE SURE YOU DESELECTED ALL OTHER OBJECTS
    bpy.ops.object.delete()
    # end of i (BED Texture)
#--------------------------------------------------


#***
#process_layers()
#***
print('>>>>>>>>>>>>>>>> DONE process_layers() <<<<<<<<<<<<<<<<')
#camera_debug()
#animate_layers()
print('>>>>>>>>>>>>>>>> DONE <<<<<<<<<<<<<<<<')

