from setuptools import setup
from setuptools.extension import Extension
from setuptools.command.build_ext import build_ext
import numpy, os, platform, sys
from os.path import join as pjoin

try:
    numpy_include = numpy.get_include()
except AttributeError:
    numpy_include = numpy.get_numpy_include()


def check_for_flag(flag_str, truemsg="", falsemsg=""):
    if flag_str in os.environ:
        enabled = os.environ[flag_str].lower() == "on"
    else:
        enabled = False

    if enabled and not truemsg == False:
        print(truemsg)
    elif not enabled and not falsemsg == False:
        print(falsemsg)
        print("   $ sudo " + flag_str + "=ON python setup.py install")
    return enabled


use_cuda = check_for_flag(
    "WITH_CUDA", "Compiling with CUDA support", "Compiling without CUDA support. To enable CUDA use:"
)
trace = check_for_flag(
    "TRACE", "Compiling with trace enabled for Bresenham's Line", "Compiling without trace enabled for Bresenham's Line"
)

print("\n--------------\n")

if platform.system().lower() == "darwin":
    os.environ["MACOSX_DEPLOYMENT_TARGET"] = platform.mac_ver()[0]
    os.environ["CC"] = "c++"


def find_in_path(name, path):
    for dir in path.split(os.pathsep):
        binpath = pjoin(dir, name)
        if os.path.exists(binpath):
            return os.path.abspath(binpath)
    return None


def locate_cuda():
    if os.path.isdir("/usr/local/cuda-10.2"):
        home = "/usr/local/cuda-10.2"
        nvcc = pjoin(home, "bin", "nvcc")
    elif os.path.isdir("/usr/local/cuda"):
        home = "/usr/local/cuda"
        nvcc = pjoin(home, "bin", "nvcc")
    elif "CUDAHOME" in os.environ:
        home = os.environ["CUDAHOME"]
        nvcc = pjoin(home, "bin", "nvcc")
    else:
        nvcc = find_in_path("nvcc", os.environ["PATH"])
        if nvcc is None:
            raise EnvironmentError("nvcc binary not found. Set $CUDAHOME or add nvcc to $PATH.")
        home = os.path.dirname(os.path.dirname(nvcc))

    cudaconfig = {"home": home, "nvcc": nvcc, "include": pjoin(home, "include"), "lib64": pjoin(home, "lib64")}
    for k, v in cudaconfig.items():
        if not os.path.exists(v):
            raise EnvironmentError(f"The CUDA {k} path could not be located in {v}")
    print("CUDA config: ", cudaconfig)
    return cudaconfig


compiler_flags = ["-w", "-std=c++11", "-O3"]
nvcc_flags = ["-arch=sm_86", "--ptxas-options=-v", "-c", "--compiler-options", "'-fPIC'", "-w", "-std=c++11", "-O3"]
include_dirs = ["../", numpy_include]
depends = ["../includes/*.h"]
sources = ["RangeLibc.pyx", "../vendor/lodepng/lodepng.cpp"]

CHUNK_SIZE = "262144"
NUM_THREADS = "256"

if use_cuda:
    compiler_flags += ["-DUSE_CUDA=1", f"-DCHUNK_SIZE={CHUNK_SIZE}", f"-DNUM_THREADS={NUM_THREADS}"]
    nvcc_flags += ["-DUSE_CUDA=1", f"-DCHUNK_SIZE={CHUNK_SIZE}", f"-DNUM_THREADS={NUM_THREADS}"]
    CUDA = locate_cuda()
    include_dirs.append(CUDA["include"])
    sources.append("../includes/kernels.cu")

if trace:
    compiler_flags.append("-D_MAKE_TRACE_MAP=1")


class custom_build_ext(build_ext):
    def build_extensions(self):
        self._customize_compiler_for_nvcc()
        super().build_extensions()

    def _customize_compiler_for_nvcc(self):
        self.compiler.src_extensions.append(".cu")
        default_compiler_so = self.compiler.compiler_so
        super_compile = self.compiler._compile

        def _compile(obj, src, ext, cc_args, extra_postargs, pp_opts):
            ext_type = os.path.splitext(src)[1]
            if ext_type == ".cu":
                self.compiler.set_executable("compiler_so", CUDA["nvcc"])
                postargs = nvcc_flags
            else:
                self.compiler.compiler_so = default_compiler_so
                postargs = compiler_flags
            super_compile(obj, src, ext, cc_args, postargs, pp_opts)
            self.compiler.compiler_so = default_compiler_so

        self.compiler._compile = _compile


if use_cuda:
    ext = Extension(
        "range_libc",
        sources,
        extra_compile_args=compiler_flags,
        extra_link_args=["-std=c++11"],
        include_dirs=include_dirs,
        library_dirs=[CUDA["lib64"], "/usr/lib/x86_64-linux-gnu"],
        libraries=["cudart"],
        runtime_library_dirs=[CUDA["lib64"]],
        depends=depends,
        language="c++",
    )
    setup(
        name="range_libc",
        author="Corey Walsh",
        version="0.1",
        ext_modules=[ext],
        cmdclass={"build_ext": custom_build_ext},
    )
else:
    setup(
        ext_modules=[
            Extension(
                "range_libc",
                sources,
                extra_compile_args=compiler_flags,
                extra_link_args=["-std=c++11"],
                include_dirs=include_dirs,
                depends=depends,
                language="c++",
            )
        ],
        name="range_libc",
        author="Corey Walsh",
        version="0.1",
        cmdclass={"build_ext": build_ext},
    )
