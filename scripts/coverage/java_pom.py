"""Ensure JaCoCo Maven plugin is declared in pom.xml before coverage runs (task A2)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

JACOCO_VERSION = "0.8.11"


def _namespace_uri(root: ET.Element) -> str:
    if root.tag.startswith("{"):
        return root.tag[1 : root.tag.index("}")]
    return ""


def _tag(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}" if ns else local


def _pom_declares_jacoco(root: ET.Element) -> bool:
    for el in root.iter():
        if el.tag.endswith("artifactId") and (el.text or "").strip() == "jacoco-maven-plugin":
            return True
    return False


def _get_or_create_build_plugins(root: ET.Element, ns: str) -> ET.Element:
    lbuild = _tag(ns, "build")
    build = None
    for ch in list(root):
        if ch.tag == lbuild:
            build = ch
            break
    if build is None:
        build = ET.SubElement(root, lbuild)

    lplugins = _tag(ns, "plugins")
    for ch in list(build):
        if ch.tag == lplugins:
            return ch
    plugins = ET.SubElement(build, lplugins)
    return plugins


def _append_jacoco_plugin(plugins: ET.Element, ns: str) -> None:
    plugin = ET.SubElement(plugins, _tag(ns, "plugin"))
    gid = ET.SubElement(plugin, _tag(ns, "groupId"))
    gid.text = "org.jacoco"
    aid = ET.SubElement(plugin, _tag(ns, "artifactId"))
    aid.text = "jacoco-maven-plugin"
    ver = ET.SubElement(plugin, _tag(ns, "version"))
    ver.text = JACOCO_VERSION

    execs = ET.SubElement(plugin, _tag(ns, "executions"))
    e1 = ET.SubElement(execs, _tag(ns, "execution"))
    g1 = ET.SubElement(e1, _tag(ns, "goals"))
    ET.SubElement(g1, _tag(ns, "goal")).text = "prepare-agent"

    e2 = ET.SubElement(execs, _tag(ns, "execution"))
    ET.SubElement(e2, _tag(ns, "id")).text = "report"
    ET.SubElement(e2, _tag(ns, "phase")).text = "test"
    g2 = ET.SubElement(e2, _tag(ns, "goals"))
    ET.SubElement(g2, _tag(ns, "goal")).text = "report"


def patch_jacoco_into_pom(pom_path: Path) -> bool:
    """Insert jacoco-maven-plugin if missing. Returns True if file was written."""
    if not pom_path.is_file():
        return False
    tree = ET.parse(pom_path)
    root = tree.getroot()
    if _pom_declares_jacoco(root):
        return False
    ns = _namespace_uri(root)
    if ns:
        ET.register_namespace("", ns)
    plugins = _get_or_create_build_plugins(root, ns)
    _append_jacoco_plugin(plugins, ns)
    ET.indent(tree.getroot(), space="  ")
    tree.write(pom_path, encoding="utf-8", xml_declaration=True)
    return True
