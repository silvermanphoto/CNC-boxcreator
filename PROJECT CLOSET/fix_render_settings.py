import bpy

def fix_render_settings():
    scene = bpy.context.scene
    
    # 1. View Transform: AgX (modern standard) or Filmic
    # "Standard" clips colors and looks bad. AgX handles bright light better.
    try:
        scene.view_settings.view_transform = 'AgX'
    except TypeError:
        # Fallback for older Blender versions
        scene.view_settings.view_transform = 'Filmic'
        
    # 2. Look: AGX often looks "flat/washed out" by default. 
    # Adding "Punchy" or "Medium High Contrast" brings back the depths.
    if scene.view_settings.view_transform == 'AgX':
        scene.view_settings.look = 'Punchy' # AgX specific look
    else:
        scene.view_settings.look = 'Medium High Contrast' # Filmic/Standard look

    # 3. Reset Levels
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    
    print(f"Applied Fixes: {scene.view_settings.view_transform} + {scene.view_settings.look}")

if __name__ == "__main__":
    fix_render_settings()
