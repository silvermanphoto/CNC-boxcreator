import sys
import os
import tkinter
from unittest.mock import MagicMock

# Mock messagebox to verify success and avoid blocking
mock_mb = MagicMock()
sys.modules['tkinter.messagebox'] = mock_mb

# Mock filedialog just in case
mock_fd = MagicMock()
sys.modules['tkinter.filedialog'] = mock_fd

import importlib.util
spec = importlib.util.spec_from_file_location("cnc_v1_26", "CNC GENERATOR - CARBIDE-OPTIMIZED v1.26.py")
cnc_v1_26 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cnc_v1_26)

def run_test():
    print("Initializing App...")
    app = cnc_v1_26.CarbideOptimizedApp()
    
    # Set Output
    target_dir = os.path.abspath("/Users/joelsilverman/Desktop/2026 Files/26-005 CNC Box Creator/CNC Plans")
    if not os.path.exists(target_dir):
        os.makedirs(target_dir)
    
    app.vars['out_folder'].set(target_dir)
    
    # Use defaults for everything else
    
    print("Running Generation...")
    app.run_generation()
    
    # Check if mock succeed was called
    # run_generation calls .showinfo("Success", ...)
    if mock_mb.showinfo.called:
        print("SUCCESS: Generation completed (showinfo called).")
        args = mock_mb.showinfo.call_args[0]
        print(f"Message: {args}")
        
        # Verify File Created
        # Look for Box SVGs v* folder
        msg = args[1]
        print(msg)
        
        # Parse final_dir from message
        if "Location: " in msg:
            final_dir = msg.split("Location: ")[1].strip()
        else:
            final_dir = "Unknown"
        
    else:
        print("FAILURE: showinfo not called.")
        if mock_mb.showerror.called:
             print("Error was shown:", mock_mb.showerror.call_args)

if __name__ == "__main__":
    run_test()
