from pydna.assembly import Assembly as Assembly_pydna
from pydna.parsers import parse_primers
from pydna.readers import read

primer = parse_primers("../test_files/primers.fas", ds=False)

# I think these are equivalent to the sequences in the test
# a = assembly.Assembly([GAL_GIN2, pCAPs_MX4blaster1_AgeI], limit=30)
a = read('dummy_a.gb')
b = read('dummy_b.gb')

asm2 = Assembly_pydna([a, b], limit=30)

print('Linear assembles: =======================================')
print()

# All the linear assemblies contain the fragments a and b once
for i, f in  enumerate(asm2.assemble_linear()):
    print("Example", i)
    print(f.figure())
    print(f.detailed_figure())

print()
print()
print()

print('Circular assembles: =======================================')
print()
candidates2 = asm2.assemble_circular()

# This particular output contains each fragment twice
chosen = candidates2[3]
print(chosen.seq.cseguid())
print(chosen.figure())


# Ignore this code
# from assembly2 import Assembly
# asm = Assembly([a, b], limit=30)

# candidates = asm.assemble_circular()

# for c in candidates:
#     print(c.seq.cseguid())
