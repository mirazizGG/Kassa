
# Script to clean up main.py lines 804 to 835
filename = r"c:\Users\u0068\Desktop\online kasssa\main.py"

with open(filename, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Users lines are 1-indexed, Python list is 0-indexed
# We want to remove lines 804 to 835
# Index start: 803
# Index end: 835 (exclusive in slice? No, 835th line is index 834. So slice up to 835)

# Verify range contents before deleting
print("Line 804:", lines[803])
print("Line 835:", lines[834])

# Remove the range [803:835] -> lines 804 to 835
# line 804 is index 803
# line 835 is index 834. To include it, we slice up to 835.
new_lines = lines[:803] + lines[835:]

with open(filename, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Cleanup complete.")
