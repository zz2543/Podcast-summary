#!/usr/bin/env python3
"""
生成 Podsum.xcodeproj/project.pbxproj。

源文件自动扫描 Podsum/ 下的全部 .swift，外加 specs/ 里的契约与 fixture——
那两处是引用而非拷贝，契约因此只有一份，不会与 spec 漂移。

新增源文件后重跑：  python3 gen-project.py
"""
import hashlib, os, pathlib

ROOT = pathlib.Path(__file__).parent
CONTRACT = "../specs/002-macos-native/contracts/PodsumModels.swift"
FIXDIR = "../specs/002-macos-native/fixtures"

def uid(seed): return hashlib.md5(seed.encode()).hexdigest()[:24].upper()

def group_of(rel):
    parts = pathlib.PurePath(rel).parts
    return parts[1] if len(parts) > 2 else "Podsum"

sources = [("PodsumModels.swift", CONTRACT, "Contracts")]
for p in sorted((ROOT / "Podsum").rglob("*.swift")):
    rel = p.relative_to(ROOT).as_posix()
    sources.append((p.name, rel, group_of(rel)))

resources = [(f, f"{FIXDIR}/{f}", "Fixtures")
             for f in sorted(os.listdir(ROOT / FIXDIR)) if f.endswith(".json")]
# 图标由 icon/make_icon.py 生成
resources.append(("Assets.xcassets", "Podsum/Assets.xcassets", "Podsum"))

for _, p, _ in sources + resources:
    assert (ROOT / p).exists(), f"缺文件: {p}"

PROJ, TARGET, PRODUCT = uid("project"), uid("target"), uid("product")
MAIN, PRODUCTS = uid("maingroup"), uid("productsgroup")
SRC_PHASE, RES_PHASE, FW_PHASE = uid("srcphase"), uid("resphase"), uid("fwphase")
PROJ_CFG, TGT_CFG = uid("projcfglist"), uid("tgtcfglist")
fref = lambda p: uid("fileref:" + p)
bfile = lambda p: uid("buildfile:" + p)

groups = {}
for name, p, g in sources + resources:
    groups.setdefault(g, []).append((name, p))

L = ["// !$*UTF8*$!", "{", "\tarchiveVersion = 1;", "\tclasses = {};",
     "\tobjectVersion = 56;", "\tobjects = {"]
w = L.append

w("\n/* Begin PBXBuildFile section */")
for name, p, _ in sources:
    w(f"\t\t{bfile(p)} /* {name} in Sources */ = {{isa = PBXBuildFile; fileRef = {fref(p)} /* {name} */; }};")
for name, p, _ in resources:
    w(f"\t\t{bfile(p)} /* {name} in Resources */ = {{isa = PBXBuildFile; fileRef = {fref(p)} /* {name} */; }};")
w("/* End PBXBuildFile section */")

w("\n/* Begin PBXFileReference section */")
w(f'\t\t{PRODUCT} /* Podsum.app */ = {{isa = PBXFileReference; explicitFileType = wrapper.application; includeInIndex = 0; path = Podsum.app; sourceTree = BUILT_PRODUCTS_DIR; }};')
for name, p, _ in sources:
    w(f'\t\t{fref(p)} /* {name} */ = {{isa = PBXFileReference; lastKnownFileType = sourcecode.swift; name = {name}; path = "{p}"; sourceTree = SOURCE_ROOT; }};')
for name, p, _ in resources:
    w(f'\t\t{fref(p)} /* {name} */ = {{isa = PBXFileReference; lastKnownFileType = {"folder.assetcatalog" if p.endswith(".xcassets") else "text.json"}; name = {name}; path = "{p}"; sourceTree = SOURCE_ROOT; }};')
w("/* End PBXFileReference section */")

w("\n/* Begin PBXFrameworksBuildPhase section */")
w(f"\t\t{FW_PHASE} = {{\n\t\t\tisa = PBXFrameworksBuildPhase;\n\t\t\tbuildActionMask = 2147483647;\n\t\t\tfiles = (\n\t\t\t);\n\t\t\trunOnlyForDeploymentPostprocessing = 0;\n\t\t}};")
w("/* End PBXFrameworksBuildPhase section */")

w("\n/* Begin PBXGroup section */")
order = ["Podsum", "Views", "Data", "Design", "Contracts", "Fixtures"]
order += [g for g in groups if g not in order]
kids = "\n".join(f"\t\t\t\t{uid('group:'+g)} /* {g} */," for g in order if g in groups)
w(f"\t\t{MAIN} = {{\n\t\t\tisa = PBXGroup;\n\t\t\tchildren = (\n{kids}\n\t\t\t\t{PRODUCTS} /* Products */,\n\t\t\t);\n\t\t\tsourceTree = \"<group>\";\n\t\t}};")
for g in order:
    if g not in groups: continue
    ks = "\n".join(f"\t\t\t\t{fref(p)} /* {n} */," for n, p in groups[g])
    w(f"\t\t{uid('group:'+g)} /* {g} */ = {{\n\t\t\tisa = PBXGroup;\n\t\t\tchildren = (\n{ks}\n\t\t\t);\n\t\t\tname = {g};\n\t\t\tsourceTree = \"<group>\";\n\t\t}};")
w(f"\t\t{PRODUCTS} /* Products */ = {{\n\t\t\tisa = PBXGroup;\n\t\t\tchildren = (\n\t\t\t\t{PRODUCT} /* Podsum.app */,\n\t\t\t);\n\t\t\tname = Products;\n\t\t\tsourceTree = \"<group>\";\n\t\t}};")
w("/* End PBXGroup section */")

w("\n/* Begin PBXNativeTarget section */")
w(f"""\t\t{TARGET} /* Podsum */ = {{
\t\t\tisa = PBXNativeTarget;
\t\t\tbuildConfigurationList = {TGT_CFG};
\t\t\tbuildPhases = (
\t\t\t\t{SRC_PHASE},
\t\t\t\t{FW_PHASE},
\t\t\t\t{RES_PHASE},
\t\t\t);
\t\t\tbuildRules = (
\t\t\t);
\t\t\tdependencies = (
\t\t\t);
\t\t\tname = Podsum;
\t\t\tproductName = Podsum;
\t\t\tproductReference = {PRODUCT} /* Podsum.app */;
\t\t\tproductType = "com.apple.product-type.application";
\t\t}};""")
w("/* End PBXNativeTarget section */")

w("\n/* Begin PBXProject section */")
w(f"""\t\t{PROJ} /* Project object */ = {{
\t\t\tisa = PBXProject;
\t\t\tattributes = {{
\t\t\t\tBuildIndependentTargetsInParallel = 1;
\t\t\t\tLastSwiftUpdateCheck = 2650;
\t\t\t\tLastUpgradeCheck = 2650;
\t\t\t\tTargetAttributes = {{
\t\t\t\t\t{TARGET} = {{
\t\t\t\t\t\tCreatedOnToolsVersion = 26.5;
\t\t\t\t\t}};
\t\t\t\t}};
\t\t\t}};
\t\t\tbuildConfigurationList = {PROJ_CFG};
\t\t\tdevelopmentRegion = en;
\t\t\thasScannedForEncodings = 0;
\t\t\tknownRegions = (
\t\t\t\ten,
\t\t\t\t"zh-Hans",
\t\t\t\tBase,
\t\t\t);
\t\t\tmainGroup = {MAIN};
\t\t\tproductRefGroup = {PRODUCTS} /* Products */;
\t\t\tprojectDirPath = "";
\t\t\tprojectRoot = "";
\t\t\ttargets = (
\t\t\t\t{TARGET} /* Podsum */,
\t\t\t);
\t\t}};""")
w("/* End PBXProject section */")

w("\n/* Begin PBXResourcesBuildPhase section */")
rf = "\n".join(f"\t\t\t\t{bfile(p)} /* {n} in Resources */," for n, p, _ in resources)
w(f"\t\t{RES_PHASE} = {{\n\t\t\tisa = PBXResourcesBuildPhase;\n\t\t\tbuildActionMask = 2147483647;\n\t\t\tfiles = (\n{rf}\n\t\t\t);\n\t\t\trunOnlyForDeploymentPostprocessing = 0;\n\t\t}};")
w("/* End PBXResourcesBuildPhase section */")

w("\n/* Begin PBXSourcesBuildPhase section */")
sf = "\n".join(f"\t\t\t\t{bfile(p)} /* {n} in Sources */," for n, p, _ in sources)
w(f"\t\t{SRC_PHASE} = {{\n\t\t\tisa = PBXSourcesBuildPhase;\n\t\t\tbuildActionMask = 2147483647;\n\t\t\tfiles = (\n{sf}\n\t\t\t);\n\t\t\trunOnlyForDeploymentPostprocessing = 0;\n\t\t}};")
w("/* End PBXSourcesBuildPhase section */")

PROJ_COMMON = """\t\t\t\tALWAYS_SEARCH_USER_PATHS = NO;
\t\t\t\tCLANG_ENABLE_MODULES = YES;
\t\t\t\tCLANG_ENABLE_OBJC_ARC = YES;
\t\t\t\tCOPY_PHASE_STRIP = NO;
\t\t\t\tENABLE_STRICT_OBJC_MSGSEND = YES;
\t\t\t\tGCC_NO_COMMON_BLOCKS = YES;
\t\t\t\tMACOSX_DEPLOYMENT_TARGET = 14.0;
\t\t\t\tSDKROOT = macosx;
\t\t\t\tSWIFT_VERSION = 5.0;"""
TGT_COMMON = """\t\t\t\tASSETCATALOG_COMPILER_APPICON_NAME = AppIcon;
\t\t\t\tASSETCATALOG_COMPILER_GLOBAL_ACCENT_COLOR_NAME = "";
\t\t\t\tCODE_SIGN_IDENTITY = "-";
\t\t\t\tCODE_SIGN_STYLE = Automatic;
\t\t\t\tCOMBINE_HIDPI_IMAGES = YES;
\t\t\t\tCURRENT_PROJECT_VERSION = 1;
\t\t\t\tENABLE_HARDENED_RUNTIME = NO;
\t\t\t\tENABLE_PREVIEWS = YES;
\t\t\t\tGENERATE_INFOPLIST_FILE = YES;
\t\t\t\tINFOPLIST_FILE = Podsum/Info.plist;
\t\t\t\tINFOPLIST_KEY_NSHumanReadableCopyright = "";
\t\t\t\tLD_RUNPATH_SEARCH_PATHS = (
\t\t\t\t\t"$(inherited)",
\t\t\t\t\t"@executable_path/../Frameworks",
\t\t\t\t);
\t\t\t\tMARKETING_VERSION = 0.1;
\t\t\t\tPRODUCT_BUNDLE_IDENTIFIER = local.podsum.macclient;
\t\t\t\tPRODUCT_NAME = "$(TARGET_NAME)";
\t\t\t\tSWIFT_EMIT_LOC_STRINGS = NO;"""

w("\n/* Begin XCBuildConfiguration section */")
for cfg, extra in [
    ("Debug", "\t\t\t\tDEBUG_INFORMATION_FORMAT = dwarf;\n\t\t\t\tENABLE_TESTABILITY = YES;\n\t\t\t\tGCC_OPTIMIZATION_LEVEL = 0;\n\t\t\t\tONLY_ACTIVE_ARCH = YES;\n\t\t\t\tSWIFT_ACTIVE_COMPILATION_CONDITIONS = DEBUG;\n\t\t\t\tSWIFT_OPTIMIZATION_LEVEL = \"-Onone\";"),
    ("Release", "\t\t\t\tDEBUG_INFORMATION_FORMAT = \"dwarf-with-dsym\";\n\t\t\t\tENABLE_NS_ASSERTIONS = NO;\n\t\t\t\tSWIFT_COMPILATION_MODE = wholemodule;"),
]:
    w(f"\t\t{uid('projcfg:'+cfg)} /* {cfg} */ = {{\n\t\t\tisa = XCBuildConfiguration;\n\t\t\tbuildSettings = {{\n{PROJ_COMMON}\n{extra}\n\t\t\t}};\n\t\t\tname = {cfg};\n\t\t}};")
    w(f"\t\t{uid('tgtcfg:'+cfg)} /* {cfg} */ = {{\n\t\t\tisa = XCBuildConfiguration;\n\t\t\tbuildSettings = {{\n{TGT_COMMON}\n\t\t\t}};\n\t\t\tname = {cfg};\n\t\t}};")
w("/* End XCBuildConfiguration section */")

w("\n/* Begin XCConfigurationList section */")
for lst, pre in [(PROJ_CFG, "projcfg:"), (TGT_CFG, "tgtcfg:")]:
    w(f"\t\t{lst} = {{\n\t\t\tisa = XCConfigurationList;\n\t\t\tbuildConfigurations = (\n\t\t\t\t{uid(pre+'Debug')} /* Debug */,\n\t\t\t\t{uid(pre+'Release')} /* Release */,\n\t\t\t);\n\t\t\tdefaultConfigurationIsVisible = 0;\n\t\t\tdefaultConfigurationName = Release;\n\t\t}};")
w("/* End XCConfigurationList section */")

w("\t};")
w(f"\trootObject = {PROJ} /* Project object */;")
w("}")

os.makedirs(ROOT / "Podsum.xcodeproj", exist_ok=True)
(ROOT / "Podsum.xcodeproj/project.pbxproj").write_text("\n".join(L) + "\n")
print(f"✓ project.pbxproj  源文件 {len(sources)} · 资源 {len(resources)}")
for _, p, g in sources:
    print(f"    [{g}] {p}")
