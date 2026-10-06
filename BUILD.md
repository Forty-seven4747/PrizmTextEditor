# TEXTEDIT（gint 移植版）— Windows 构建与安装（不用 WSL、不用 GiteaPC）

这是编辑器的 **gint 内核**版本。和原 PrizmSDK 版不同，它用 gint 的 POSIX
文件接口（`open/read/write/close` + `opendir/readdir`）在计算器**真实存储内存**
（`/TEXTEDIT/` 下）读写真正的 `.txt` 文件——因为 gint 直接驱动闪存，绕开了
OS 的 `Bfile_*` 限制（那个限制把存储写入锁死了，所有 `Bfile_*` 调用都返回 -5）。

> **为什么用 gint：** 目标固件上每个 `Bfile_*` 调用都返回 `-5`（EAGAIN）——存储
> 只能枚举、写入被锁。gint 是替代内核；用它，`open/read/write/close` 和
> `opendir/readdir` 能操作真实存储文件（PythonExtra 能读写文件也正是因为这个）。

---

## 0. 关键事实：GiteaPC 是可选的

gint 生态的**官方推荐**是 Linux / WSL + GiteaPC。但 GiteaPC 本身**只是自动化脚本**：
它读取每个仓库头部的 `# giteapc: depends=...`，按依赖顺序到各仓库里跑
`make -f giteapc.make configure build install`。

**所以你可以完全不用 GiteaPC**——直接克隆这几个仓库，手动按顺序跑它们自带的
`giteapc.make`。整条链只需要 **MSYS2**（Windows 上的 POSIX 环境），**不需要 WSL**。
交叉工具链是从源码编译的（binutils + GCC），所以第一次会慢（10–40 分钟），但之后
就能一直用。binutils 的 `configure.sh` 里本身就带 `pacman`（MSYS2）分支，说明这条路
是走得通的。

### 两条路，二选一

- **路线 A（推荐先试，最省事）**：用 **预编译工具链**。gint 官方安装页
  <https://gint.lephenixnoir.fr/en/install.html> 会列出 Windows / MSYS2 的预编译包
  （免去从源码编译 GCC）。**注意：我这个环境打不开那个域名**，没法帮你核对确切的
  仓库地址/命令，请你在自己机器上打开该页，按它给的 pacman 配置装。
  *该页若能访问，装完直接跳到第 8 节。*
- **路线 B（本文详述，保证可用）**：**MSYS2 + 从源码手动编译**。下面从第 1 节开始，
  一条命令不落地照抄即可。

> ⚠️ **诚实提醒：** fxSDK 官方文档白纸黑字写着「Windows 本身不受支持，官方只支持
> WSL 里的 Ubuntu」。但整个构建就是标准的 `autotools`（binutils/GCC）+ `cmake`
> （fxsdk/gint），这些在 MSYS2 里都能跑，binutils 脚本也内置了 MSYS2 的 pacman 分支。
> 也就是说：**不是官方背书，但实测能通**。若你遇到无法解决的 MSYS2 怪问题，
> 最后的兜底才是 WSL（见第 12 节末）。

> **MSYS2 的坑（已替你踩过）：** `msys` 仓库很精简，**没有** `libpng` / `libusb` /
> `libjpeg` / `python-pillow`（这些只有 `mingw-w64-*` 版本，另一套 ABI 不能混用）。
> 而 fxSDK 和 Pillow 又硬性需要它们，所以要**额外从源码编三个库**（见第 2.1 节）。

### 0.1 一键脚本（推荐）

第 3–8 节的所有步骤已打包成一个脚本：**`~/build_all.sh`**
（即 `E:\msys64\home\Zhen\build_all.sh`）。在你的 **"MSYS2 MSYS"** 终端里：

```sh
pacman -S --needed base-devel ca-certificates git make diffutils flex bison texinfo xz \
    curl wget tar patch gperf autoconf automake libtool m4 gcc cmake pkgconf \
    gmp-devel mpfr-devel mpc-devel isl-devel zlib-devel ncurses-devel python python-pip
bash ~/build_all.sh
```

它会按 1→6 顺序编 **binutils → gcc → OpenLibm → fxlibc → gint → textedit**
（**OpenLibm 必须在 fxlibc 之前**，见 §6），
结尾打印 `textedit.g3a` 的路径。要点：

- 脚本在 `~/bld/` 下的**全新目录**里构建 binutils/gcc，**不依赖也不会碰**任何旧的
  或被锁的源码树（避免 Windows 上删不掉的残留目录卡住整个流程）。
- 依赖 `~/fakebin/pacman`（假 pacman，跳过 giteapc 的坏依赖检查）和已下载的
  `~/sh-elf-binutils/binutils-2.42.tar.xz`、`~/sh-elf-gcc/gcc-14.1.0.tar.xz`。
- **PATH 顺序**：脚本把 **`$SYSROOT/bin` 放在 `~/.local/bin` 之前**
  （`SYSROOT="$HOME/.local/share/fxsdk/sysroot"`）。这不是可有可无的——见 §12 的
  「`cannot execute 'cc1'`」：MSYS2 上 `ln -s` 会退化成**复制**，`~/.local/bin` 里的
  `sh-elf-gcc` 只是一份副本，它按自身位置推出 prefix=`~/.local`，于是去
  `~/.local/libexec/...` 找 `cc1`，扑空。而 `$SYSROOT/bin` 里的是「原位」二进制，
  gcc 相对自身定位就能找到 `cc1`/`libgcc`/`as`/`ld`。
- 前置：第 2.1 节的 libpng/libusb/libjpeg/Pillow 必须已装（脚本不含这步）。
- 首次全跑约 **40–80 分钟**（大头是 gcc 编译）。

下面第 1–8 节是同样的流程的**逐步说明**，粘性的排错细节都在那里。

---

## 1. 安装 MSYS2

1. 去 <https://www.msys2.org/> 下安装包，双击安装（默认装到 `C:\msys64` 即可）。
2. **重要**：用开始菜单里的 **"MSYS2 MSYS"**（不是 MINGW64 / UCRT64）打开终端。
   编译交叉工具链需要在纯 POSIX 环境里做，`autotools` 才认。
3. **下面的所有命令都在同一个 MSYS2 MSYS 终端里连续执行**（因为我们要靠 `export`
   的 `PATH` 串起来）。

---

## 2. 在 MSYS2 里装编译依赖

```sh
pacman -Syu                 # 更新（若提示关窗重开，就重开这个 MSYS 终端再来）
pacman -S --needed \
    base-devel ca-certificates git make diffutils flex bison texinfo xz curl wget tar patch gperf \
    autoconf automake libtool m4 \
    gcc cmake pkgconf \
    gmp-devel mpfr-devel mpc-devel isl-devel zlib-devel ncurses-devel \
    python python-pip
```

说明（**这几个包名跟 Debian/Ubuntu 完全不一样，别照抄 apt 的名字**）：

- `base-devel` / `gcc` / `make` 是**宿主编译器**，用来编译交叉工具链本身。
- **编译 GCC 要的是 `-devel` 头文件包**：`gmp-devel`、`mpfr-devel`、`mpc-devel`
  （`mpc-devel` 会顺带拉上另外两个），外加 `isl-devel`、`zlib-devel`。
  - ⚠️ **`libmpc` 这个名字在 msys 仓库里根本不存在**——MPC 的包名是 `mpc`
    （运行库，`gcc` 已经依赖它），**头文件在 `mpc-devel`**。同理 GMP/MPFR 是
    `gmp`/`mpfr`（运行库）+ `gmp-devel`/`mpfr-devel`（头文件）。
- `ncurses-devel` 给 fxSDK 用；`gperf`/`bison`/`flex` 给 GCC 的构建脚本用。
- **UDisks2 在 MSYS2 里没有**——第 3 节会用一个开关关掉它（不影响构建）。

### 2.1 补三个 msys 仓库里没有的库：libpng、libusb、libjpeg（+ 装 Pillow）

`msys` 仓库里**没有** `libpng`、`libusb`、`libjpeg`、`python-pillow` 这几个包
（只有 `mingw-w64-*` 版本，另一套 ABI，不能混用）。但：

- **fxSDK 的 `CMakeLists.txt` 硬性要求** `libpng16` 和 `libusb-1.0`
  （`pkg_check_modules(... REQUIRED ...)`，**没有**关闭它们的开关）；
- **Pillow 从源码编译时硬性要求 jpeg**（12.x 起，报
  `required dependency ... jpeg`），而 msys 没有任何 jpeg 包。

所以这三个库要**从源码编译**，装到 `/usr/local`，再编 Pillow。

> **网络注意（国内常见坑）：** 若 `ca-certificates` 已装，`curl` 连 github.com /
> SourceForge 仍报 `(60) unable to get local issuer certificate` 或 `(56) Connection
> reset`，那是**网络层被中间人改证书 / 直接 reset**（pacman 走国内镜像不受影响）。
> 应急办法：把下载命令里的 `curl -L -O` 换成 `curl -LkO`（`-k` 跳过证书校验），
> 或给 URL 加国内代理前缀（如 `https://ghproxy.net/https://github.com/...`）。

```sh
# --- 先装 CA 证书（否则 curl 报 (60) SSL 证书验证失败）---
pacman -S --needed ca-certificates

# 证书正常时用这个；被拦就改成 CURL="curl -LkO"，或给 URL 加国内代理前缀
CURL="curl -L -O"

# --- libpng（依赖 zlib-devel，上面已装）---
# 别用 SourceForge：它会重定向到镜像站，国内常被 reset（curl 56）。
# 改用 GitHub 源码（仓库里没带 configure，要先 autogen）。
$CURL https://github.com/pnggroup/libpng/archive/refs/tags/v1.6.44.tar.gz
tar xf v1.6.44.tar.gz && cd libpng-1.6.44
./autogen.sh || autoreconf -fi
./configure --prefix=/usr/local && make -j"$(nproc)" && make install
cd ~

# --- libusb ---
$CURL https://github.com/libusb/libusb/releases/download/v1.0.27/libusb-1.0.27.tar.bz2
tar xf libusb-1.0.27.tar.bz2 && cd libusb-1.0.27
./configure --prefix=/usr/local && make -j"$(nproc)" && make install
cd ~

# --- libjpeg-turbo（Pillow 12 源码编译必需）---
$CURL https://github.com/libjpeg-turbo/libjpeg-turbo/releases/download/3.2.0/libjpeg-turbo-3.2.0.tar.gz
tar xf libjpeg-turbo-3.2.0.tar.gz && cd libjpeg-turbo-3.2.0
cmake -B build -DWITH_SIMD=0 -DCMAKE_INSTALL_PREFIX=/usr/local
cmake --build build -j"$(nproc)" && cmake --install build
cd ~

# 让 pkg-config / 编译器找得到 /usr/local
export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:$PKG_CONFIG_PATH
export CFLAGS="-I/usr/local/include"
export LDFLAGS="-L/usr/local/lib"
echo 'export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:$PKG_CONFIG_PATH' >> ~/.bashrc

# --- 装 Pillow（MSYS2 Python 受 PEP 668 保护，必须 --break-system-packages）---
python -m pip install --break-system-packages pillow
python -c "import PIL; print(PIL.__version__)"

# 验证三个库（应各打印一个版本号）
pkg-config --modversion libpng16 libusb-1.0 ncurses
```

> **Pillow 必须用 `--break-system-packages`**：MSYS2 的 Python 受 PEP 668「外部管理」
> 保护，不加会报 `externally-managed-environment`；而 msys 仓库又没有 `python-pillow`
> 包。对 Pillow 这种叶子库没风险。**必须先编好 libjpeg 再装 Pillow**，否则会报
> `The headers or library files could not be found for jpeg`。Pillow 的 sdist 会被
> pip 缓存，补装 libjpeg 后重跑**不会**重下那几十 MB。

> 版本号（libpng 1.6.44、libusb 1.0.27、libjpeg-turbo 3.2.0）只是写下时的最新值；
> 若下载 404，去 <https://github.com/pnggroup/libpng/tags>、
> <https://github.com/libusb/libusb/releases>、
> <https://github.com/libjpeg-turbo/libjpeg-turbo/releases> 换成当时的版本。

### 2.2 依赖总清单（一眼看全，省得一个个试）

整条链**只会用到下面这些库**，不会再有别的：

| 库（pkg-config 名） | 谁要它 | msys 仓库有没有 | 怎么解决 |
|---|---|---|---|
| `gmp`/`mpfr`/`mpc`/`isl`/`zlib` | 编交叉 GCC | ✅ 有 `-devel` 包 | 第 2 节 pacman |
| `ncurses` | fxSDK 的 fxlink | ✅ `ncurses-devel` | 第 2 节 pacman |
| `libpng16` | fxSDK 的 fxgxa/fxlink | ❌ | 第 2.1 节源码编 ✅ |
| `libusb-1.0` | fxSDK 的 fxlink | ❌ | 第 2.1 节源码编 ✅ |
| `jpeg` | Pillow（源码编译） | ❌ | 第 2.1 节源码编 ✅ |
| **`sdl2`** | fxSDK 的 fxlink（SDL 渲染） | ❌ | **关掉**：cmake 加 `-DFXLINK_DISABLE_SDL2=1` |
| **`udisks2`** | fxSDK 的 fxlink（自动挂载） | ❌ | **关掉**：cmake 加 `-DFXLINK_DISABLE_UDISKS2=1` |
| `Pillow`(PIL) | fxconv 转图片/字体 | ❌ | 第 2.1 节 pip ✅ |

要点：

- **fxSDK 一共只查这 5 个 pkg-config 模块**：`libpng16`、`libusb-1.0`、`ncurses`
  （恒定必需）+ `sdl2`、`udisks2`（可用开关关掉）。前三个我们已备齐；后两个在 msys
  仓库里没有，且**只跟 fxlink 的 USB/渲染有关**，编 `.g3a` 根本用不到——所以直接关掉。
- **后面几步（binutils / gcc / fxlibc / openlibm / gint）不再需要任何额外 host 库**，
  它们只用交叉工具链 + 已装的 gmp/mpfr/mpc/isl/zlib。
- Python 侧 fxconv 也只依赖 **Pillow** 一个（不需要 yaml/toml；`project.toml` 用
  Python 3.11+ 内置的 `tomllib` 读）。

把本地 bin 目录加进 PATH（`fxsdk`、`sh-elf-gcc` 等最终都装在这）：

```sh
export PATH="$HOME/.local/bin:$PATH"
```

建议把这行也追加到 `~/.bashrc`，以后新开终端自动生效：

```sh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
```

---

## 3. 装 fxSDK（提供 `fxsdk` 命令和 sysroot）

fxSDK 必须**最先**装：binutils/GCC 都要装进它的 sysroot 里，而且它的 `util.sh`
会调用 `fxsdk path sysroot` 来定位。

```sh
cd ~
git clone https://git.planet-casio.com/Lephenixnoir/fxsdk
cd fxsdk
cmake -B build -DCMAKE_INSTALL_PREFIX="$HOME/.local" \
    -DFXLINK_DISABLE_UDISKS2=1 -DFXLINK_DISABLE_SDL2=1
cmake --build build
cmake --install build
cd ..
```

验证并拿到 sysroot 路径：

```sh
fxsdk --version
fxsdk path sysroot          # 记下这个路径，后面 binutils/GCC 会装进去
```

> **两个 `-DFXLINK_DISABLE_*=1` 必须在 MSYS2 里加**：msys 仓库既没有 `udisks2` 也没有
> `sdl2`，不关掉 cmake 会直接停在 `Package 'sdl2' not found`。它们只影响 fxlink 的
> 自动挂载/USB 发送功能，**不影响编 `.g3a`**。
>
> 若 cmake 在旧 build 目录里卡住，先 `rm -rf build` 再重跑这条 cmake。
>
> **如果你 `cmake --build` 时报 `be32toh`/`be16toh` 隐式声明（implicit declaration）**：
> 这是 fxSDK 的移植 bug——`fxgxa/endianness.h` 只处理了 `__APPLE__` 和 `__linux__`，
> Cygwin/MSYS 一个都匹配不上。补一个分支即可（把下面这段追加到该文件 `#elif
> defined(__linux__)` 那段之后、`#endif` 之前）：
>
> ```c
> #else
>   /* Cygwin/MSYS: 无 be*toh，用 GCC 内建字节交换（x86 小端） */
>   #include <stdint.h>
>   #define htobe16(x) __builtin_bswap16(x)
>   #define be16toh(x) __builtin_bswap16(x)
>   #define htole16(x) (x)
>   #define le16toh(x) (x)
>   #define htobe32(x) __builtin_bswap32(x)
>   #define be32toh(x) __builtin_bswap32(x)
>   #define htole32(x) (x)
>   #define le32toh(x) (x)
>   #define htobe64(x) __builtin_bswap64(x)
>   #define be64toh(x) __builtin_bswap64(x)
>   #define htole64(x) (x)
>   #define le64toh(x) (x)
> ```
>
> 改完重新 `cmake --build build && cmake --install build` 即可。**注意：重新 clone
> fxSDK 会丢掉这个改动，要重打。**

### 3.1 另外两个 Cygwin/MSYS 移植 bug（同样要打，否则 fxlink 编不过）

在 MSYS2 里编译 fxSDK 时，`libusb.h` 会（经 `<windows.h>`）把一堆 Windows 宏带进来，
和 fxSDK 自己的标识符撞名。实测要再打两处补丁：

**(a) `fxlink/tui/tui-interactive.c`：`IN`/`OUT` 是 Windows 宏**

`tui-interactive.c` 大约第 205 行有这两个局部指针，`IN`/`OUT` 被展开成 `winnt.h` 里的
空宏，报 `error: expected identifier or '(' before '=' token`。把这两个局部变量改名即可：

```c
/* 原样（会报错）：
   struct fxlink_transfer *IN  = comm->ftransfer_IN;
   struct fxlink_transfer *OUT = comm->ftransfer_OUT; */
struct fxlink_transfer *tr_IN  = comm->ftransfer_IN;
struct fxlink_transfer *tr_OUT = comm->ftransfer_OUT;
```

（同函数里用到它们的 4 处也跟着改：`if(IN)`→`if(tr_IN)`、`IN->msg.size`→`tr_IN->msg.size`
等；字符串字面量 `"IN"`/`"OUT"` 不用动。）

**(b) `libfxlink/include/fxlink/defs.h`：`min`/`max` 是 Windows 宏**

`gdb-bridge.c` 先 include 了 `libusb.h`（→`windows.h`，定义了 `min`/`max` 宏），
随后 `defs.h` 里的 `static inline int min(...)` 就报 `expected identifier ... before 'int'`。
在 `defs.h` 第 16 行（`#include <poll.h>` 之后、`static inline int min` 之前）插一段：

```c
#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif
```

改完 `cmake --build build && cmake --install build`，直到不再报错、`cmake --install`
能装出 `fxlink.exe` + `fxsdk-gdb-bridge.exe` 为止。

### 3.2 第三个 Cygwin 移植 bug：**gcc 自己的 `fputs_unlocked`**（改 `sh-elf-gcc/configure.sh`）

这一处不在 fxSDK，而在 **sh-elf-gcc 上**。症状是 binutils 编完后，gcc 编译到一半报：

```
../../gcc-14.1.0/gcc/system.h:150:33: error: 'fputs_unlocked' was not declared in this scope;
  did you mean 'fputc_unlocked'?
make[2]: *** [Makefile:2542: sh.o] Error 1
```

**根因**（逐行核实过）：

- Cygwin 的 `<stdio.h>` 把 `clearerr/feof/ferror/fileno/fflush/fgetc/fputc/fread/fwrite_unlocked`
  放在 `#if __MISC_VISIBLE`（默认开）里 → **有声明**；
- 但 **`fgets_unlocked` / `fputs_unlocked` 在 `#if __GNU_VISIBLE` 里**，只有定义
  `_GNU_SOURCE` 才可见 —— **GCC 编自己时不定义 `_GNU_SOURCE`**；
- gcc 的 `gcc/system.h` 注释也写着「`fputs/fwrite/fprintf_unlocked` 是扩展，需手工
  prototype」，但那段手工 `extern` 被
  `#  if defined (HAVE_DECL_FPUTS_UNLOCKED) && !HAVE_DECL_FPUTS_UNLOCKED` 包着，
  而 configure 在 Cygwin 上把 `HAVE_DECL_FPUTS_UNLOCKED` **误判为 1** → 整段被跳过；
- 于是 `#define fputs(...) fputs_unlocked(...)` 之后，无人声明 `fputs_unlocked` → 报错。

**修法**：在 `~/sh-elf-gcc/configure.sh` 里、**提取块之后、configure 之前**（且**不能**
放进 `if [[ -d 已解压目录 ]]` 的 `else` 里，否则重用已解压目录时不生效），加一行把
`system.h` 里所有这类守卫强制为真（共 11 处；幂等；签名与 Cygwin 兼容，`__restrict`
会被忽略，不会撞名）：

```sh
sed -i -E 's|^#  if defined \(HAVE_DECL_[A-Z_]+_UNLOCKED\) && !HAVE_DECL_[A-Z_]+_UNLOCKED$|#  if 1|' "gcc-$VERSION/gcc/system.h"
```

> `$` 锚点能匹配，是因为 `system.h` 来自 GNU 官方 tar.xz（LF）；这段 `sed` 作用的是
> `system.h` 而非 `configure.sh`，所以脚本本身是 LF/CRLF 都不影响它。

**⚠️ 两个必须记住的坑（本会话真踩了）：**

1. **`git archive HEAD` 只导 HEAD，不导工作区**。`build_all.sh` 用
   `git -C ~/sh-elf-gcc archive HEAD | tar -x` 取脚本；你若改了 `configure.sh` 却**没
   `git commit`**，导出到 `~/bld/gcc/` 的仍是旧脚本 → 上述 `sed` 白打、gcc 照样失败。
   → 改完立刻提交，并 `git show HEAD:configure.sh | grep -c 'HAVE_DECL_'` 确认 HEAD 里有。
2. **该仓库开了 `core.autocrlf`**（git 会警告 `LF will be replaced by CRLF`），
   `git archive` 出来的 `*.sh` 是 **CRLF**。虽然 MSYS2 bash 多数情况能忍，但会让 `\`
   续行、结尾带引号的文件名参数变得可疑。**在 `tar -x` 之后统一去 CR**：
   `sed -i 's/\r$//' *.sh giteapc.make 2>/dev/null`（`patches/*.patch` 同理）。

（`build_all.sh` 已把这两件事都写进去了：gcc 段 tar -x 后紧跟去 CR，且 `configure.sh`
的 `sed` 写成单行、不依赖 `\` 续行。）

---

## 4. 装 sh-elf-binutils（交叉汇编器/链接器）

```sh
cd ~
git clone --depth 1 https://git.planet-casio.com/Lephenixnoir/sh-elf-binutils
cd sh-elf-binutils

# (1) 预下载源码，绕开 ftpmirror.gnu.org 的 302 跳转（可能跳到被墙的镜像）
curl -L --fail -o binutils-2.42.tar.xz \
    https://mirrors.tuna.tsinghua.edu.cn/gnu/binutils/binutils-2.42.tar.xz

# (2) 放一个假的 pacman，阻止 configure.sh 误判依赖缺失后弹交互式 sudo
mkdir -p ~/fakebin && printf '#!/bin/sh\nexit 0\n' > ~/fakebin/pacman && chmod +x ~/fakebin/pacman

export PATH="$HOME/.local/bin:$HOME/fakebin:$PATH"
make -f giteapc.make configure build install PREFIX="$HOME/.local"
cd ..
```

> **为什么要那两步（这是 MSYS2 专属的坑）：**
> - `configure.sh` 里写死了 `URL=https://ftpmirror.gnu.org/...`，那是个 **302 跳转**，
>   在国内常跳到被墙/被 reset 的镜像。**只要先把同名 tar.xz 放在仓库目录**，
>   脚本会打印 `Found ..., skipping download` 直接跳过下载。版本号见 `giteapc.make`。
> - `configure.sh` 用 `pacman -Qi libmpc / libpng / ppl` 来查依赖，可**这几个名字在
>   msys 仓库里根本不存在**（真实名是 `mpc`，且没有 ppl）。于是它判定「缺依赖」，
>   会 **`read` 一个 Y/n 然后自己 `sudo pacman -S`**——MSYS2 没 `sudo`，要么报错要么
>   卡住等你输入。放一个 `-Qi` 恒返回 0 的假 `pacman` 在最前 PATH，就能静默跳过这一步。
>   （第 2 节的真依赖早已装齐，这个假 `pacman` 全程不会被真正用到。）

验证：

```sh
sh-elf-ld --version
```

- 版本（当前 **2.42**）固定写在仓库的 `giteapc.make` 里，不用你填。
- 耗时约 5–10 分钟（源码约 27 MB，用 TUNA 镜像几秒就下完）。
- 构建日志在 `~/sh-elf-binutils/build/giteapc-{configure,build,install}.log`，
  失败时先看这里。

---

## 5. 装 sh-elf-gcc（交叉 C 编译器）

```sh
cd ~
git clone --depth 1 https://git.planet-casio.com/Lephenixnoir/sh-elf-gcc
cd sh-elf-gcc

# (1) 预下载 GCC 源码（约 90 MB），同样绕开 ftpmirror.gnu.org
curl -L --fail -o gcc-14.1.0.tar.xz \
    https://mirrors.tuna.tsinghua.edu.cn/gnu/gcc/gcc-14.1.0/gcc-14.1.0.tar.xz

# (2) 同一个假 pacman + PATH
export PATH="$HOME/.local/bin:$HOME/fakebin:$PATH"
make -f giteapc.make configure build install PREFIX="$HOME/.local"
cd ..
```

- 版本（当前 **14.1.0**）也固定在 `giteapc.make` 里。
- **这一步最慢**：编译 20–40 分钟（源码解压后就地编）。
- 它会跑 `./contrib/download_prerequisites` 去 `gcc.gnu.org/pub/gcc/infrastructure/`
  下 gmp/mpfr/mpc/isl（**实测 gcc.gnu.org 直连通，返回 200**，不像 github 会被拦）；
  若那步失败，也可改用第 2 节已装的 `gmp-devel/mpfr-devel/mpc-devel/isl-devel`。
- 我们的编辑器是**纯 C**，所以第一遍装完就够用——**不需要**「装完 libc 再跑第二遍
  编 libstdc++」的双趟流程（那是给 C++ 项目用的）。
- 日志在 `~/sh-elf-gcc/build/giteapc-*.log`。

验证：

```sh
sh-elf-gcc --version        # 应打印 14.1.0
```

---

## 6. 装 OpenLibm 和 fxlibc（gint 依赖的数学库 + C 运行时）

gint 依赖这两个库，必须先装进 sysroot。**顺序很重要：先 OpenLibm，再 fxlibc。**

原因（giteapc 元数据也写着 `fxlibc depends=...,OpenLibm`）：fxlibc 的 3rdparty
`grisu2b_59_56` **无条件** `#include <openlibm.h>`（见 `3rdparty/grisu2b_59_56/k_comp.h`；
`CMakeLists.txt` 里该文件直接列进 SOURCES，没有开关可关），所以 fxlibc 编译时**必须**已经能
搜到 `openlibm.h`。反过来 OpenLibm 是自足的：它自带 `sh3eb/{ctype,string,assert}.h` 桩，
并以 `-ffreestanding -nostdlib` 编译（于是 gcc 用自带的 `stdint.h`），**不需要** fxlibc。

> 踩坑记录：先编 fxlibc 会报
> `3rdparty/grisu2b_59_56/k_comp.h:26:10: fatal error: openlibm.h: No such file or directory`。

### 6.1 OpenLibm（普通 Makefile 工程）

```sh
cd ~
git clone https://git.planet-casio.com/Lephenixnoir/OpenLibm
cd OpenLibm
make -j4 USEGCC=1 TOOLPREFIX=sh-elf- AR=sh-elf-ar CC=sh-elf-gcc \
    libdir="$(fxsdk path lib)" includedir="$(fxsdk path include)" \
    install-static-superh install-headers-superh
cd ..
```

- `install-headers-superh` 把 `openlibm.h`/`openlibm_math.h`/… 装到
  `$(fxsdk path include)` = **`$SYSROOT/sh3eb-elf/include`** —— 这**正好是 gcc 默认会搜的目录**
  （`sh-elf-gcc -E -v` 可见），所以之后的 fxlibc 能直接 `#include <openlibm.h>`。
- `install-static-superh` = `install-static`（装 `libopenlibm.a` 到 `$(fxsdk path lib)`）+ 顺手
  把 `libm.a` 链过去。
- **必须带 `CC=sh-elf-gcc`**：Makefile 用 `$(CC) -dumpmachine` 判架构（得 `sh3eb-elf` → `ARCH=sh3eb`），
  才会选对 `sh3eb` 源集（含它自带的 ctype/string 桩与 `-m3 -mb`）；否则会走错架构。

### 6.2 fxlibc（CMake 工程，依赖 6.1 装好的 openlibm.h）

```sh
cd ~
git clone https://git.planet-casio.com/Vhex-Kernel-Core/fxlibc
cd fxlibc
cmake -B build-gint -DFXLIBC_TARGET=gint -DCMAKE_TOOLCHAIN_FILE=cmake/toolchain-sh.cmake
cmake --build build-gint -j4
cmake --install build-gint
cd ..
```

（`-DFXLIBC_TARGET=gint` 时**不要**指定 prefix；它用 `fxsdk path include/lib` 的动态路径，
即 `$SYSROOT/sh3eb-elf/{include,lib}`。）

---

## 7. 装 gint（内核 + SDK）

```sh
cd ~
git clone https://git.planet-casio.com/Lephenixnoir/gint
cd gint
fxsdk build-cg -c            # 配置（可选；想加 -DGINT_USER_VRAM=1 之类就写这里）
fxsdk build-cg               # 编译
fxsdk build-cg install       # 安装
cd ..
```

`build-cg` 是 fx-CG 系列（fx-CG10/20/50、Graph 90+E）。fx-9860G 用 `build-fx`。

---

## 8. 构建 textedit → textedit.g3a

> **重要（已实测）：新版 gint（本仓库版本）是纯 CMake 工程，仓库里根本没有
> `Makefile.include`。** 所以老式的 `-include $(GINT)/Makefile.include` 写法**不成立**。
> 本工程已改用 **fxSDK 的「Makefile 风格」工程**：`project.cfg`（配置）＋ `Makefile`
> （fxSDK 模板），gint 的头文件/`libgint-cg.a`/`fxcg50.ld` 都由 gint 装进 sysroot，
> 由 `fxsdk build-cg`（或直接 `make`）驱动。**不再需要 `GINT` 环境变量。**

只需 PATH 里有 `sh-elf-gcc` 和 `fxsdk`，然后（注意 MSYS2 里 E: 盘挂在 `/e`）：

```sh
export PATH="$HOME/.local/bin:$PATH"
cd /e/Desktop/textedit/gint-port
fxsdk build-cg          # 等价于：make all-cg（等价于：make）
```

产出 **`textedit.g3a`**（就在 `gint-port/` 里）。

（`project.cfg` 里的 `NAME := textedit` 决定输出文件名；`NAME_G3A := TextEdit` 是
显示在计算器图标上的标题。`ICON_CG_UNS` → `assets/icon-uns.png`、`ICON_CG_SEL` →
`assets/icon-sel.png`，两张 92×64 的菜单图标（未选中：白纸 + 光标；选中：白纸上
打出 `PRIZM!` 且光标在末尾），交给 `fxgxa --g3a` 打包。）

> **关于 `project.toml`：** 本工程目录里那个 `project.toml` **是多余的**——已核实
> 当前 fxSDK/fxconv 里**没有任何代码读它**（名称/图标都来自 CMake 参数或 `project.cfg`），
> 留着无害但可忽略。真正生效的是 `project.cfg` + `Makefile`。

### 8.1 源码层要适配当前 gint 的两处（已改，实测可出 `.g3a`）

**(a) 文本测量 API 变了：`dsize` / `dnsize`**

当前 gint（`gint/display.h`）的签名是：

```c
void dsize (char const *str,        font_t const *font, int *w, int *h);
void dnsize(char const *str, int size, font_t const *font, int *w, int *h);
```

两点变化：① 多了一个 `font_t const *font` 参数（传 `NULL` 就用 `dfont()` 设定的字体，即
gint 默认字体）；② **不再有第 4 个 "line height" 出参**——行高现在直接从 `*h` 得到
（源码 `src/render/topti.c`：`if(h) *h = f->line_height;`）。旧代码给的 4 参形式会报
`expected 'const font_t *' but argument is of type 'int *'` / `too few arguments`。

本工程 `src/main.c` 已按新 API 改（4 处）：

```c
/* measure_font() */
int w = 0, h = 0;
dsize("M", NULL, &w, &h);      if(h > 0) g_FH = h;  if(w > 0) g_FW = w;
/* input_name() */
int cw = 0, ch = 0; dnsize(out, len, NULL, &cw, &ch);
/* notice() */
int w = 0, h = 0;   dsize(msg, NULL, &w, &h);
/* editor_session() */
dnsize(L->d + sub, g_curCol - sub, NULL, &cx, &ch);
```

**(b) 用到 libc 就必须把 `-lc -lopenlibm` 加进 `LIBS_CG`**

fxSDK 模板的 `project.cfg` 里 `LIBS_CG` 是**空的**——因为模板的 `main.c` 只用 gint
自带的 `dprint`/`dtext`，不碰 libc。本工程用的是**真 libc**（`malloc/free/realloc/
strlen/memcpy/strncpy/strcmp/strchr/snprintf/remove/...`），所以必须显式链接 fxlibc
与 OpenLibm，否则为**链接期**报一堆 `undefined reference to '_malloc' / '_strlen' / ...`：

```cfg
LIBS_FX := -lc -lopenlibm
LIBS_CG := -lc -lopenlibm
```

依据：gint 自己的 CMake 流程就是这么连的——`cmake/FindGint.cmake` 里
`Gint::Fxlibc` 指向 `libc.a`，`Gint::Gint` 的 `INTERFACE_LINK_LIBRARIES` 是
`"-lopenlibm;-lgcc"`，并且让 Gint ↔ Fxlibc **互相** `target_link_libraries`
（解内核与 libc 的循环引用）。Makefile 流程里 `LDFLAGS_CG` 已经
`-lgint-cg ... -lgint-cg` 写了两次，正好对应这个循环。

> 链接末尾会有一条 `warning: ... has a LOAD segment with RWX permissions`——
> 这是新版 binutils 对 gint 链接脚本的常规提示，**无害**，可以忽略。

---

## 9. 装到计算器

1. 把 `textedit.g3a` 拷到 fx-CG 的存储里（USB 连电脑选「USB 大容量存储 / 数据」模式，
   丢进根目录）。
2. 断开；插件出现在主菜单，打开它。
3. 首次运行会在存储内存创建 `/TEXTEDIT/`。
4. **F1** = 新建文件（输名字，EXE 确认），打字，**F1** 保存，**F5** 回浏览器，
   **F2** 上级目录，**F3** 删除，**F4** 新建文件夹，**EXE** 打开文件 / 进入文件夹。

---

## 10. 验证它是真存储（不是 MCS）

用 USB 大容量模式把计算器连电脑。你应该能看到一个 **`TEXTEDIT`** 文件夹，里面是
你保存的 **`.txt`** 文件——这些是 PC 能直接读的真实文件，就像 PythonExtra 的文件
浏览器产出的那样。这正是 gint 移植的意义。

---

## 11. 工程结构

```
gint-port/
├── project.cfg       # fxSDK 工程配置（NAME / 图标 / CFLAGS / LDFLAGS）——生效的是这个
├── Makefile          # fxSDK 模板 Makefile（fxsdk build-cg / make all-cg 驱动）
├── project.toml      # 遗留多余文件（当前 fxSDK/fxconv 不读它，可忽略）
├── gen_icon.py       # 重新生成下面两张 92x64 菜单图标（纯 stdlib）
├── assets/
│   ├── icon-uns.png  # 未选中：白纸 + 光标
│   └── icon-sel.png  # 选中：白纸上打出 PRIZM!，光标在末尾
└── src/
    ├── main.c        # 编辑器 + 存储浏览器（gint POSIX 文件 I/O）
    ├── keymap.h
    └── keymap.c      # 键位矩阵 -> 字符 映射（取自 PythonExtra，MIT）
```

---

## 12. 排错 / 已知限制

**常见问题：**

- `curl: (60) ... unable to get local issuer certificate` → 先 `pacman -S ca-certificates`；
  若**已装仍报**，就是网络层在做 TLS 中间人（国内直连 GitHub 常见），改用 `curl -LkO`
  或国内代理前缀（见第 2.1 节）。
- `curl: (56) Recv failure: Connection reset`（SourceForge 尤甚）→ 换 GitHub 直链
  （第 2.1 节已是 GitHub）。若 GitHub 也卡，可给 URL 加代理前缀（如
  `https://ghproxy.net/https://github.com/...`，可用性自行甄别）。
- `fxsdk: command not found` → 忘了 `export PATH="$HOME/.local/bin:$PATH"`。
- `sh-elf-gcc: command not found`（在装 fxlibc 时）→ 同上，PATH 没带上 `.local/bin`。
- **`sh-elf-gcc: fatal error: cannot execute 'cc1': spawn: No such file or directory`**
  （cmake 里表现为 `Check for working C compiler: .../sh-elf-gcc.exe - broken`）：
  **MSYS2 上 `ln -s` 会静默退化成复制**，所以 install.sh「Symlinking sysroot binaries
  to ~/.local/bin」出来的其实是一堆**副本**（`ls -la` 是普通文件、`readlink -f` 指向自己、
  大小等同 sysroot 原文件）。这个副本按自身位置推出 `prefix=~/.local`，于是去
  `~/.local/libexec/gcc/sh3eb-elf/14.1.0/cc1` 找 `cc1`，但 `cc1` 其实在
  **sysroot** 的 `libexec/` 里 → 报错。（验证：`sh-elf-gcc -print-prog-name=cc1`
  只回一个裸 `cc1` 即为此症。）
  **修法**：让 `sh-elf-gcc` 用 **sysroot 里的「原位」二进制**——把 `$SYSROOT/bin`
  放到 PATH 最前：
  ```sh
  SYSROOT="$HOME/.local/share/fxsdk/sysroot"      # 或 $(fxsdk path sysroot)
  export PATH="$SYSROOT/bin:$PATH"                # 必须在 ~/.local/bin 之前
  sh-elf-gcc -print-prog-name=cc1                 # 应打印 .../sysroot/libexec/.../cc1.exe
  ```
  原理：gcc 相对**自身二进制位置**定位 `cc1`/`libgcc`/`as`/`ld`；从 `$SYSROOT/bin`
  启动时 prefix 即 `$SYSROOT`，`libexec/`、`lib/gcc/`、`sh3eb-elf/bin/` 全部命中。
  （`~/build_all.sh` 已内置此 PATH 顺序，并在 gcc 装好后加了一次「trivial compile」自检。）
- `configure.sh` 里冒出 `sudo: command not found` → 第 2 节依赖没装齐，手动
  `pacman -S <缺的包>` 再重跑该仓库的 `make -f giteapc.make configure build install`。
- GCC 编译报缺 `gmp/mpfr/mpc` 头文件 → `pacman -S gmp-devel mpfr-devel mpc-devel
  isl-devel zlib-devel` 后重跑第 5 节。（**不是** `libmpc`——那个名字在 msys 里不存在。）
- `pip install pillow` 报 `externally-managed-environment` → 加 `--break-system-packages`
  （第 2.1 节）。
- `pip install pillow` 报 `could not be found for jpeg` → 先按第 2.1 节编好
  libjpeg-turbo，再重跑（sdist 已缓存，不重下）。
- fxSDK 配置阶段报 `libpng16 not found` 或 `libusb-1.0 not found` → 第 2.1 节的
  libpng/libusb 没装好，或忘了 `export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:...`。
- 构建 `textedit.g3a` 报找不到 `Makefile.include` → 见第 8 节的说明。

**已知限制：**

- 构建链很长（binutils+gcc 从源码编），首次全跑约 40–80 分钟。本文每一步都在
  用户的 MSYS2（`E:\msys64`）里实测过；若重装，照 §2→§7 顺序即可。
- 现代 gint 是 CMake 工程、不带 `Makefile.include`，故本工程走 fxSDK 的
  `project.cfg` + `Makefile` 风格（见 §8）。
- 无滚动条、无搜索、暂不支持 UTF-8 / 非 ASCII 文本（Casio 字体是 ASCII）。
- 文件列表上限 `MAX_ENTRIES`（512），文档上限 `MAX_LINES`（1500）。
- 保存是整文件重写（`O_TRUNC`）；对文本编辑器没问题，不适合超大文件。

**最后兜底（不推荐，仅在 MSYS2 彻底走不通时）：**
官方唯一支持的是 **WSL + Ubuntu + GiteaPC**。若你改主意，最省心的顺序仍是
`wsl --install` → Ubuntu 里用 `apt` 装依赖 → 装 GiteaPC → `giteapc install
Lephenixnoir/sh-elf-gcc fxsdk gint`。本文路线 B 只是把这几步**拆成手工、搬到
MSYS2**，逻辑完全一样。
