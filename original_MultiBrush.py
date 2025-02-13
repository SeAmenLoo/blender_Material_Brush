bl_info = {
    'name': 'Material Brush',
    'author': 'Francisco Elizade, Daniel Grauer',
    'version': (1, 0, 2),
    'blender': (2, 90, 0),
    'location': 'View3D - Texture Paint mode',
    'description': 'Paint all texture layers of materials simultaneously',
    'category': 'Image Paint',
    'wiki_url': 'https://github.com/kromar/blender_Material_Brush',
}

import bpy
import math
import random
import copy
import string
import time
from bpy.utils import register_class, unregister_class
from bpy.props import IntProperty, StringProperty, CollectionProperty, EnumProperty
from bpy.types import Panel, UIList, Operator, PropertyGroup

def profiler(start_time=None, string=None): 
    if not start_time:
        start_time = time.time()
    elapsed = time.time()
    print("{:.6f}".format((elapsed - start_time) * 1000), "ms << ", string)  
    
    return start_time  


# return name of selected object
def get_activeSceneObject():
    return bpy.context.scene.objects.active.name



# ui list item actions
class Uilist_actions(Operator):
    bl_idname = "listbrushmats.list_action"
    bl_label = "List Action"

    action: EnumProperty(
        items=(
            ('SAVE', "Up", ""),
            ('LOAD', "Down", ""),
            ('UPDATE', "Update", ""),
        )
    )    
    #temp_image = {}

    def invoke(self, context, event):        
        
        # List of brush materials
        scene = context.scene
        ob = context.active_object
        idx = scene.brush_index  
        self.temp_image = []
        
        brush_id = context.scene.brush_index

        #Operators inside lists    
        try:
            item = scene.listbrushmats[idx]
        except IndexError:
            pass
                
        if self.action == 'UPDATE':           
            scene.listbrushmats.clear()                            
            for i in range(len(bpy.data.materials)):
                if(bpy.data.materials[i]): # != context.active_object.active_material):
                    item = scene.listbrushmats.add()
                    item.id = len(scene.listbrushmats)
                    item.name = bpy.data.materials[i].name
                scene.brush_index = 0
            self.report({'INFO'}, "Updated Brush List")

        
        elif self.action == 'SAVE':
            #Save temporal image by texture_paint_slots in active object
            for i in range(len(bpy.context.object.active_material.texture_paint_slots)):
                chkslot = context.active_object.active_material.texture_paint_slots[i]
                if(chkslot != None):
                    tempimage = bpy.context.object.active_material.texture_paint_images[i].name
                    bpy.data.images[tempimage].save()
                    #chkslot.texture.image.save()            
                    self.report({'INFO'}, "Saved Images")
            #pass
        
        elif self.action == 'LOAD':
            #reload saved temporal images to texture_paint_slots in active object
            #make sure we did not change last active object.
            for i in range(len(bpy.context.object.active_material.texture_paint_slots)):
                chkslot = context.active_object.active_material.texture_paint_slots[i]
                if(chkslot != None):
                    tempimage = bpy.context.object.active_material.texture_paint_images[i].name
                    #tempimage = bpy.data.images.find(context.active_object.active_material.texture_paint_slots[i].texture.image.name)
                    bpy.data.images[tempimage].reload() 
                    #bpy.ops.image.reload()
                    self.report({'INFO'}, "Reloaded Images")
                    
            for area in context.screen.areas:
                if area.type in ['IMAGE_EDITOR', 'VIEW_3D']:
                    area.tag_redraw()
            #bpy.ops.wm.redraw_timer(type='DRAW', iterations=1)
            #pass            
        
        return {"FINISHED"}             


# custom list
class MP_UL_brushitems(UIList):    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if item.name == context.active_object.active_material.name:            
            layout.prop(item, "name", text="", emboss=False, translate=False, icon='NODE_MATERIAL')
        else:
            layout.prop(item, "name", text="", emboss=False, translate=False, icon='BRUSH_TEXDRAW')
        #split = layout.split(factor=0.7)
        #split.label(text="Index: %d" % (index))

    def invoke(self, context, event):
        pass
    
    
# draw the panel
class UIListMaterial(Panel):
    """Creates a Panel in the Object properties window"""
    bl_idname = 'OBJECT_PT_my_panel'
    bl_space_type = 'VIEW_3D'    
    bl_region_type = 'UI'
    bl_category = 'Tool'
    bl_context = 'imagepaint'
    bl_label = "Material Brush"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        rows = 2
        row = layout.row()
        row.label(text="Select Brush")
        col = row.column(align=True)
        col.operator("listbrushmats.list_action", icon='FILE_REFRESH', text="Update List").action = 'UPDATE'
                
        row = layout.row()
        row.template_list("MP_UL_brushitems", "", scene, "listbrushmats", scene, "brush_index", rows=rows)  

        row = layout.row()
        row.label(text="Alt+Left Mouse Button to paint")
        #layout.label(text="Save Painted Material")
        row = layout.row(align=True)
        row.operator("listbrushmats.list_action", text = "Save").action = 'SAVE'
        row.operator("listbrushmats.list_action", text = "Discard").action = 'LOAD'
                
        #set the texfaces using this material.
        brush_id = context.scene.brush_index      #brush iNdex    
        main(context, brush_id)


# Create custom property group
class CustomProp(PropertyGroup):
    '''name:  StringProperty() '''
    id: IntProperty()
    test: IntProperty()
    #temp_images = []
    
#start_time = None
class material_paint(Operator):
    '''Paint material layers'''
    bl_idname = "paint.material_paint"
    bl_label = "Material paint"
    bl_options = {'REGISTER', 'UNDO'}
    time = 0
    stroke = []
    texture_slot_matrix = []

    def fill_brush_stroke(self, x, y):       
        brushstroke = {
            "name": "defaultStroke",
            "pen_flip": False,
            "is_start": False,
            "location": (0,0,0),
            "mouse": (x, y),
            #"mouse_event": (0.0, 0.0),
            "pressure": 1,
            "size": bpy.context.tool_settings.unified_paint_settings.size,
            "time": self.time,
            #"x_tilt": 0,
            #"y_tilt": 0
            }               
        return brushstroke
    

    def stroke_mode(self, event, stroke): 
        if (self.lastmapmode == 'RANDOM'):
                bpy.context.tool_settings.image_paint.brush.texture_slot.map_mode = 'TILED'
                bpy.context.tool_settings.image_paint.brush.texture_slot.offset[0] = random.uniform(-2.0, 2.0)
                bpy.context.tool_settings.image_paint.brush.texture_slot.offset[1] = random.uniform(-2.0, 2.0)
            
        elif (self.lastmapmode == 'VIEW_PLANE'):
            bpy.context.tool_settings.image_paint.brush.texture_slot.map_mode = 'TILED'
            # map_mode = 'View Plane'
            offset_x = event.mouse_region_x - (bpy.context.region.width/2)
            offset_x = offset_x / stroke[0]["size"]
            bpy.context.tool_settings.image_paint.brush.texture_slot.offset[0] = offset_x * -1            
            offset_y = event.mouse_region_y - (bpy.context.region.height/2)
            offset_y = offset_y / stroke[0]["size"]
            bpy.context.tool_settings.image_paint.brush.texture_slot.offset[1] = offset_y * -1 - math.ceil(stroke[0]["size"] / 25)
            #self.offset = offset_x, offset_y
            #self.execute(context)
            #context.area.header_text_set("Offset %.4f %.4f" % tuple(self.offset))


    def collect_strokes(self, context, event):
        self.stroke = []    ## TODO: create new stroke list
        brushstroke = self.fill_brush_stroke(event.mouse_region_x, event.mouse_region_y) 
        brushstroke["is_start"] = True
        self.stroke.append(copy.deepcopy(brushstroke))
        brushstroke["is_start"] = False
        self.stroke.append(brushstroke)
        args = (self, context)                
        x = self.stroke[0]["mouse"][0]
        y = self.stroke[0]["mouse"][1]             
        
        stroke = []     ## TODO: why use local stroke? create new local stroke list?
        self.time = 0
        stroke.append(self.fill_brush_stroke(x, y))
        stroke[0]["is_start"] = True    
        
        """
        print("SELF STROKE 1: \n", 40*"=")
        print(self.stroke) 
        print("\nSTROKE 1: \n", stroke)
        print(40*"=")   
        #"""
        
        return stroke
            
           
    def node_finder(self, material):
        
        start_time = profiler(time.time(), "Start paint Profiling")
        texture_maps = {}


        def follow_node_links(mat_node):
            for node_input in mat_node.inputs:
                for node_link in node_input.links:   
                    # when image is found identify the type
                    if node_link.from_node.bl_static_type == 'TEX_IMAGE' and node_link.from_node.image:
                                        
                        # Direct texture to BSDF_PRINCIPLED node connection 
                        #('Base Color', 'Roughness', 
                        if node_link.to_node.bl_static_type == 'BSDF_PRINCIPLED':
                            #print(node_input.name, node_link.from_node.image.name) 
                            texture_maps[node_input.name] = node_link.from_node.image.name
                        # indirect connection (NORMAL, BUMP, DISPLACEMENT) 
                        else:                    
                            #print(node_link.to_node.bl_static_type, node_link.from_node.image.name)
                            texture_maps[node_link.to_node.bl_static_type] = node_link.from_node.image.name
                            
                        
                        #print('image name: ', node_link.from_node.image.name) 
                        #print("node input: ", node_input.name)  
                        #print("going to node: ", node_link.to_node.bl_static_type, '\n') 
                        
                        #print("going to node: ", node_link.is_valid)                    
                        #print("going to node: ", node_link.from_node.name)
                        #print("going to node: ", node_link.from_node.bl_idname)
                        #print("going to node: ", node_link.from_node.bl_static_type)                 
                        #print("going to node: ", node_link.to_node.name)               
                        #print("going to node: ", node_link.to_node.bl_idname)                            
                        
                    # keep going down the rabit hole to find all those textures
                    follow_node_links(node_link.from_node)   
                    

        for mat_node in material.node_tree.nodes:
            if mat_node.type == 'OUTPUT_MATERIAL':
                # we start at the material output node
                #print("\nStarting at: ",  mat_node.name)
                follow_node_links(mat_node)

        start_time = profiler(start_time, "node finder")
        return texture_maps

    def create_texture_slot_matrix(self):
        brush_id = bpy.context.scene.brush_index   
        material_maps = self.node_finder(bpy.context.object.active_material)   
        brush_maps = self.node_finder(bpy.data.materials[brush_id])

        # function to return key for any value
        def get_dict_key(dict, val):
            for key, value in dict.items():
                if val == value:
                    return key 
            return "key doesn't exist"

        texture_slot_matrix = []
        for i in range(len(bpy.data.materials[brush_id].texture_paint_slots)):
        #for i in range(len(bpy.context.object.active_material.texture_paint_slots)):
            #print("\ni: ", i)
            bs = bpy.data.materials[brush_id].texture_paint_images[i].name
            ms = bpy.context.object.active_material.texture_paint_images[i]
            
            #print("brush texture: ", bs)
            
            bs_type = get_dict_key(brush_maps, bs)
            ms_texture = material_maps[bs_type]
            #print("Brush type", bs_type)
            #print("Material texture", ms_texture, '\n')
            
            #now get the index of that texture 
            for m in range(len(bpy.context.object.active_material.texture_paint_slots)):
                if ms_texture in bpy.context.object.active_material.texture_paint_images[m].name:
                    #print(m, ms_texture)
                    texture_slot_matrix.append(m)                    
                    
        #print(texture_slot_matrix)
        return texture_slot_matrix

   
    def paint_strokes(self, brush_id, sstroke):
        #start_time = profiler(time.time(), "Start paint Profiling")

        ## TODO: replace this part with the new node texture system 
        #bpy.context.tool_settings.image_paint.brush.texture_slot.offset[1] -= move_y

        #print("\n\nBrush: ", bpy.data.materials[brush_id].name, "\nmaterial: ", bpy.context.object.active_material.name)
        #print(len(bpy.data.materials[brush_id].texture_paint_slots))
        if bpy.context.object.active_material.use_nodes and bpy.data.materials[brush_id].use_nodes:   
                
            #start_time = profiler(start_time, "paint brush 0")
            for i in range(len(bpy.data.materials[brush_id].texture_paint_slots)):
            #for i in range(len(bpy.context.object.active_material.texture_paint_slots)):                
                
                #start_time = profiler(start_time, "paint brush 1")
                # check if brush material contains texture paint slots 
                # #(image texture nodes are considered texture paint slots)
                if bpy.data.materials[brush_id].texture_paint_slots[i]:
                    image = bpy.data.materials[brush_id].texture_paint_images[i]                    
                    brush_slot = image.name
                    #print("brush slots: ", brush_slot)
                    #create textures if they do not exists, they are required for painting

                    if image.name not in bpy.data.textures:
                        texture = bpy.data.textures.new(image.name, 'IMAGE')
                        bpy.data.textures[texture.name].image = image
                    # this is the brush texture slot used for painting
                    brush_texture_slot = bpy.data.textures[brush_slot]        
                    bpy.context.tool_settings.image_paint.brush.texture = brush_texture_slot

                    
                    # paint if active material contains texture slots
                    m = self.texture_slot_matrix[i]
                    if bpy.context.object.active_material.texture_paint_slots[m]:
                        #print("mats slot: ", bpy.context.object.active_material.texture_paint_images[m].name, "\n")
                        bpy.context.object.active_material.paint_active_slot = m    
                        #print(brush_stroke, "\n\n")      
                        #start_time = profiler(start_time, "paint brush 3")        
                        bpy.ops.paint.image_paint(stroke=sstroke) 
                        
            #start_time = profiler(start_time, "paint brush 4")
            
        else:
            self.report({'WARNING'}, 'Material Node disabled')
            

    @classmethod
    def poll(cls, context):
        return bpy.ops.paint.image_paint.poll()

   
    def modal(self, context, event): 
        #print(event.pressure)

        if event.type in {'MOUSEMOVE'}:    
            #start_time = profiler(time.time(), "Start modal Profiling")  
            #""" 
            stroke  = self.collect_strokes(context, event)
            brush_id = context.scene.brush_index
            move_x = event.mouse_region_x - self.last_mouse_x
            move_y = event.mouse_region_y - self.last_mouse_y
            move_length = math.sqrt(move_x * move_x + move_y * move_y)            
            brush_spacing = stroke[0]["size"] * 2 * (context.tool_settings.image_paint.brush.spacing / 100) #40
            
            #start_time = profiler(start_time, "modal profile 1")

            if (move_length >= brush_spacing):      #context.tool_settings.image_paint.brush.spacing
                self.stroke_mode(event, stroke)
                
                #start_time = profiler(start_time, "modal profile 2")

                if(context.tool_settings.image_paint.brush.texture_slot.use_random == True):
                    randomangle = context.tool_settings.image_paint.brush.texture_slot.random_angle
                    context.tool_settings.image_paint.brush.texture_slot.angle = random.uniform(0.0, randomangle)              
                elif(context.tool_settings.image_paint.brush.texture_slot.use_rake == True):
                    angcos = move_x / move_length
                    angsin = move_y / move_length
                    angle = math.atan2(angsin, angcos)
                    if(angle < 0):
                           angle = math.pi - angle
                    context.tool_settings.image_paint.brush.texture_slot.angle = angle 
                
                    #self.offset = angcos, angle
                    #self.execute(context)
                    #context.area.header_text_set("Offset %.4f %.4f" % tuple(self.offset))
                
                #context.tool_settings.image_paint.brush.texture_slot.offset[1] -= move_y
                #event.mouse_region_x / context.region.width
                
                #start_time = profiler(start_time, "modal profile 3")
                self.paint_strokes(brush_id, stroke)                   
                #start_time = profiler(start_time, "modal profile 4")                     
                self.last_mouse_x = event.mouse_region_x
                self.last_mouse_y = event.mouse_region_y
            self.time = 0            
            self.stroke.clear() 
            #"""
            
            #start_time = profiler(start_time, "modal profile 5")
       
        elif event.value in {'RELEASE'} or event.type in {'ESC'}:
            context.tool_settings.image_paint.brush.texture_slot.angle = self.lastangle
            context.tool_settings.image_paint.brush.texture_slot.map_mode = self.lastmapmode
            context.tool_settings.image_paint.brush.texture = self.lastBrush
            context.object.active_material.paint_active_slot = self.lastSlot
            context.tool_settings.image_paint.brush.texture_slot.offset[0]=0
            context.tool_settings.image_paint.brush.texture_slot.offset[1]=0
            #types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'}

        return {'PASS_THROUGH'}   
    

            
    def invoke(self, context, event):
        #start_time = profiler(time.time(), "Start invoke Profiling")
        if event.type in {'LEFTMOUSE'}:
            self.last_mouse_x = event.mouse_region_x
            self.last_mouse_y = event.mouse_region_y            
            self.lastangle = context.tool_settings.image_paint.brush.texture_slot.angle
            self.lastmapmode = context.tool_settings.image_paint.brush.texture_slot.map_mode
            self.lastBrush = context.tool_settings.image_paint.brush.texture
            self.lastSlot = context.object.active_material.paint_active_slot 
            
            #start_time = profiler(start_time, "invoke profile 1")      
            stroke  = self.collect_strokes(context, event)            
            #start_time = profiler(start_time, "invoke profile 2")
         
            self.stroke_mode(event, stroke)      
            #start_time = profiler(start_time, "invoke profile 3")

            if(context.tool_settings.image_paint.brush.texture_slot.use_random == True):
                randomangle = context.tool_settings.image_paint.brush.texture_slot.random_angle
                context.tool_settings.image_paint.brush.texture_slot.angle = random.uniform(0.0, randomangle)
            
            elif(context.tool_settings.image_paint.brush.texture_slot.use_rake == True):
                    #angcos = move_x / move_length
                    #angsin = move_y / move_length
                    #angle = math.atan2(angsin, angcos)
                    context.tool_settings.image_paint.brush.texture_slot.angle = 0
                     
            brush_id = context.scene.brush_index   
            """ material_maps = self.node_finder(bpy.context.object.active_material)   
            brush_maps = self.node_finder(bpy.data.materials[brush_id])
            print('material maps:\n', bpy.context.object.active_material.name, material_maps)  
            print('brush maps:\n', bpy.data.materials[brush_id].name, brush_maps) """

            
            self.texture_slot_matrix = self.create_texture_slot_matrix()

            self.paint_strokes(brush_id, stroke)      
            #start_time = profiler(start_time, "invoke profile 4")
            self.time = 0            
            self.stroke.clear()
            context.window_manager.modal_handler_add(self)
        
        #start_time = profiler(start_time, "total draw profile")
        return {'RUNNING_MODAL'}
    

def main(context, brush_id):
    #brush_id is the index of the texture in the brush material list
    ob = context.active_object
    
    def invoke(self, context, event):
        info = 'Lets %s ' % ('see')
        self.report({'INFO'}, info)


classes = (
    Uilist_actions,
    MP_UL_brushitems,
    UIListMaterial,
    CustomProp,
    material_paint,    
    )


def register():    
    [bpy.utils.register_class(c) for c in classes]

    bpy.types.Scene.listbrushmats = CollectionProperty(type=CustomProp)
    km = bpy.context.window_manager.keyconfigs.default.keymaps['Image Paint']
    kmi = km.keymap_items.new("paint.material_paint", 'LEFTMOUSE', 'PRESS', alt=True)
    bpy.types.Scene.brush_index = IntProperty()
    #bpy.types.Scene.brush_slots_num = IntProperty()
    
    #bpy.types.Scene.listmaterials = CollectionProperty(type=CustomProp)
    #bpy.types.Scene.custom_index = IntProperty()


def unregister():    
    [bpy.utils.unregister_class(c) for c in classes]
        
    del bpy.types.Scene.listbrushmats
    km = bpy.context.window_manager.keyconfigs.default.keymaps['Image Paint']
    kmi = km.keymap_items.find('paint.material_paint')
    km.keymap_items.remove(km.keymap_items[kmi])
    
    del bpy.types.Scene.brush_index
    #bpy.types.Scene.brush_slots_num = IntProperty()
    
    
    #del bpy.types.Scene.listmaterials
    #del bpy.types.Scene.custom_index

if __name__ == "__main__":
    register()