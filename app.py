import pymupdf # Updated from fitz
import re
import random
from datetime import datetime, timedelta

def generate_otdr_batch(input_pdf, end_index=12):
    # 1. Open the base PDF using the new pymupdf syntax
    doc = pymupdf.open(input_pdf)
    page = doc[0]
    text = page.get_text("text")

    print(f"\nAnalyzing Environment for: {input_pdf}")

    # Dynamic Start Index & Decoupled ID Extraction
    file_match = re.search(r'Fiber(\d+)\.trc', text)
    base_file_num = int(file_match.group(1)) if file_match else 4
    
    start_index = base_file_num + 1
    
    if start_index > end_index:
        print(f"Error: Start index ({start_index}) exceeds end index ({end_index}).")
        doc.close()
        return

    id_match = re.search(r'Fiber ID:\s*Fiber(\d+)', text)
    base_id_num = int(id_match.group(1)) if id_match else 18

    # 3. Max Date Logic
    dates = re.findall(r'\d{2}/\d{2}/\d{4}', text)
    if dates:
        max_date_str = max(dates, key=lambda d: datetime.strptime(d, "%d/%m/%Y"))
    else:
        max_date_str = "24/08/2026" 
        
    test_date_match = re.search(r'Test date:\s*(\d{2}/\d{2}/\d{4})', text)
    original_test_date = test_date_match.group(1) if test_date_match else None

    # --- 4. Base Time Extraction ---
    time_match = re.search(r'\d{2}:\d{2}:\d{2}', text)
    if time_match:
        current_time = datetime.strptime(time_match.group(0), "%H:%M:%S")
    else:
        current_time = datetime.strptime("12:00:00", "%H:%M:%S") 

    # 5. Topology Detection & Math Extraction
    splice_match = re.search(r'Average splice loss:\s*([\d\.]+)', text)
    mode = "SPLICE_PRESENT" if splice_match else "SINGLE_SPAN"
    
    print(f"Detected Base Trace : Fiber{base_file_num}.trc")
    print(f"Target Generation   : Files {start_index} through {end_index}")
    print(f"Topology Mode       : {mode}")
    print(f"Max Date Override   : {max_date_str}\n")

    span_len_match = re.search(r'Span length:\s*([\d\.]+)\s*km', text)
    span_loss_match = re.search(r'Span loss:\s*([\d\.]+)\s*dB', text)
    
    if not span_len_match or not span_loss_match:
        print("Error: Could not find Span Length or Span Loss in the document.")
        doc.close()
        return

    span_len = float(span_len_match.group(1))
    orig_span_loss = float(span_loss_match.group(1))
    orig_avg_loss = round(orig_span_loss / span_len, 3)

    # 6. Generation Loop
    for i in range(start_index, end_index + 1):
        replacements = {}

        # A. Identity Updates
        new_file_name = f"Fiber{i}.trc"
        id_offset = base_id_num + (i - base_file_num)
        new_fiber_id = f"Fiber{id_offset}"
        
        replacements[f"Fiber{base_file_num}.trc"] = new_file_name
        replacements[f"Fiber{base_id_num}"] = new_fiber_id

        # B. Date & Time Updates
        if original_test_date and original_test_date != max_date_str:
            replacements[original_test_date] = max_date_str

        time_gap = timedelta(minutes=random.randint(4, 12), seconds=random.randint(0, 59))
        current_time += time_gap
        replacements[time_match.group(0)] = current_time.strftime("%H:%M:%S")

        # C. Mathematical Randomization
        if mode == "SINGLE_SPAN":
            new_span_loss = round(orig_span_loss * random.uniform(0.90, 1.10), 3)
            new_avg_loss = round(new_span_loss / span_len, 3)
            
            replacements[f"{orig_span_loss:.3f}"] = f"{new_span_loss:.3f}"
            replacements[f"{orig_avg_loss:.3f}"] = f"{new_avg_loss:.3f}"
            
        elif mode == "SPLICE_PRESENT":
            # 1. Extract the original splice loss
            orig_splice = float(splice_match.group(1))
            
            # 2. Randomize the splice loss by +/- 10%
            new_splice = round(orig_splice * random.uniform(0.90, 1.10), 3)
            
            # 3. Calculate how much the overall trace changed based on the new splice
            loss_difference = new_splice - orig_splice
            new_span_loss = round(orig_span_loss + loss_difference, 3)
            new_avg_loss = round(new_span_loss / span_len, 3)
            
            # 4. Target the strings for replacement
            replacements[f"{orig_span_loss:.3f}"] = f"{new_span_loss:.3f}"
            replacements[f"{orig_avg_loss:.3f}"] = f"{new_avg_loss:.3f}"
            replacements[f"{orig_splice:.3f}"] = f"{new_splice:.3f}"

        # 7. Apply Redactions and Insertions
        new_doc = pymupdf.open(input_pdf)

        # Replace longer strings first to prevent substring conflicts.
        sorted_replacements = dict(
            sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True)
        )
        
        for page_num in range(len(new_doc)):
            current_page = new_doc[page_num]
            
            for old_text, new_text in sorted_replacements.items():
                instances = current_page.search_for(old_text)
                
                for inst in instances:
                    # EXFO report values use a consistent font size.
                    original_fontsize = 9.5

                    current_page.add_redact_annot(inst)
                    current_page.apply_redactions()
                    
                    expanded_box = pymupdf.Rect(
                        inst.x0, inst.y0 - 2, inst.x1 + 60, inst.y1 + 5
                    )

                    text_color = (0, 0.5, 0) if new_text == f"{new_span_loss:.3f}" else (0, 0, 0)

                    current_page.insert_textbox(
                        expanded_box,
                        new_text, 
                        fontsize=original_fontsize, 
                        fontname="helv", 
                        color=text_color, 
                        align=0
                    )

        # 8. Save the newly generated file
        output_filename = f"{new_file_name.replace('.trc', '')}.pdf"
        new_doc.save(output_filename)
        new_doc.close()
        
        print(f"Generated: {output_filename} | ID: {new_fiber_id} | Time: {replacements[time_match.group(0)]} | Span: {new_span_loss:.3f} | Avg: {new_avg_loss:.3f}")

    doc.close()
    print("\n--- Batch Generation Complete ---")

if __name__ == "__main__":
    # Ensure this matches the exact file name in your folder
    generate_otdr_batch("Fiber4.pdf")