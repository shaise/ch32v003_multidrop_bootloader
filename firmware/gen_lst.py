from SCons.Script import Import
import os

Import("env")

toolchain = env.PioPlatform().get_package_dir("toolchain-riscv")
objdump = os.path.join(toolchain, "bin", "riscv-none-embed-objdump")

elf = env.subst("$BUILD_DIR/${PROGNAME}.elf")
lst = env.subst("$BUILD_DIR/${PROGNAME}.lst")

env.AddPostAction(
    elf,
    env.VerboseAction(
        f'"{objdump}" -h -S -C "{elf}" > "{lst}"',
        "Generating ${TARGET}.lst"
    )
)
