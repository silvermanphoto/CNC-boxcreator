
def verify_encasement():
    # --- INPUTS (Proposed Parameters) ---
    p_width = 62.4594   # inches
    p_height = 43.4594  # inches
    p_depth = 5.0984    # inches
    p_stock_mm = 15.2   # mm
    
    # --- TARGETS (Inner Object) ---
    target_inner_w = 61.2  # inches
    target_inner_h = 42.2  # inches
    target_inner_d = 4.5   # inches
    
    target_clearance = 0.0625 # 1/16" friction/slide fit
    
    # --- CALCULATIONS ---
    # Convert Stock to Inches
    stock_in = p_stock_mm / 25.4
    
    # Calculate Resulting Internal Dimensions from Parameters
    # Internal = External - (2 * Stock)
    calc_inner_w = p_width - (2 * stock_in)
    calc_inner_h = p_height - (2 * stock_in)
    
    # Calculate Resulting Internal Depth
    # Depth = External - (1 * Back Panel Stock)  (Assuming open front / lid separate)
    # The user plan calculated p_depth = 4.5 + stock.
    # So Internal Depth should be p_depth - stock.
    calc_inner_d = p_depth - stock_in
    
    # --- VERIFICATION ---
    print(f"--- VERIFICATION REPORT ---")
    print(f"Proposed External Params: W={p_width:.4f}\", H={p_height:.4f}\", D={p_depth:.4f}\"")
    print(f"Stock Thickness: {p_stock_mm}mm ({stock_in:.5f}\")")
    print(f"Target Inner Object: {target_inner_w}\" x {target_inner_h}\" x {target_inner_d}\"")
    print(f"Target Clearance: {target_clearance}\"")
    print("-" * 30)
    
    # 1. Width Check
    expected_w = target_inner_w + target_clearance
    diff_w = calc_inner_w - expected_w
    print(f"Internal Width: {calc_inner_w:.4f}\"")
    print(f"  > Target (Obj + Clr): {expected_w:.4f}\"")
    print(f"  > Diff: {diff_w:.5f}\" [{'MATCH' if abs(diff_w) < 0.001 else 'FAIL'}]")
    
    # 2. Height Check
    expected_h = target_inner_h + target_clearance
    diff_h = calc_inner_h - expected_h
    print(f"Internal Height: {calc_inner_h:.4f}\"")
    print(f"  > Target (Obj + Clr): {expected_h:.4f}\"")
    print(f"  > Diff: {diff_h:.5f}\" [{'MATCH' if abs(diff_h) < 0.001 else 'FAIL'}]")
    
    # 3. Depth Check (Assuming NO clearance added to depth in plan, just exact fit + stock)
    # Plan said: "Depth: 4.5 + 0.5984252 (Back Panel) + 0.0 = 5.0984"
    expected_d = target_inner_d 
    diff_d = calc_inner_d - expected_d
    print(f"Internal Depth: {calc_inner_d:.4f}\"")
    print(f"  > Target (Obj Only): {expected_d:.4f}\"")
    print(f"  > Diff: {diff_d:.5f}\" [{'MATCH' if abs(diff_d) < 0.001 else 'FAIL'}]")
    
    print("-" * 30)
    if abs(diff_w) < 0.001 and abs(diff_h) < 0.001 and abs(diff_d) < 0.001:
        print("RESULT: SUCCESS. The parameters will exactly encase the object with specified tolerance.")
    else:
        print("RESULT: FAIL. Discrepancies found.")

if __name__ == "__main__":
    verify_encasement()
