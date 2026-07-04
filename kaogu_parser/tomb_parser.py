"""
In-memory tomb parser for web use.
Adapted from the 考古文献解析 skill's tomb_parser.py.
"""

import re
import json
import csv
import io


class WebTombParser:
    """In-memory parser with export utilities. No file I/O."""

    def __init__(self, report_name: str, content: str):
        self.report_name = report_name
        self.text = content
        self.lines = content.splitlines(keepends=True)
        self.tombs: list[dict] = []
        self.source_note = ""

    # ------------------------------------------------------------------
    # Tomb management
    # ------------------------------------------------------------------

    def add_tomb(self, tomb: dict):
        defaults = {
            "墓葬编号": "", "年代": "", "墓向": "", "墓葬形制": "",
            "墓口长": None, "墓口宽": None, "墓深": None,
            "发掘位置": "", "层位": "", "备注": "",
            "随葬器物": []
        }
        entry = {**defaults, **tomb}
        art_defaults = {
            "器物编号": "", "器物名称": "", "材质": "", "器型": "",
            "数量": 1, "特征描述": ""
        }
        entry["随葬器物"] = [
            {**art_defaults, **a} for a in entry.get("随葬器物", [])
        ]
        self.tombs.append(entry)

    def add_tombs(self, tombs: list[dict]):
        for t in tombs:
            self.add_tomb(t)

    # ------------------------------------------------------------------
    # Search helpers
    # ------------------------------------------------------------------

    def grep(self, pattern: str, flags=0) -> list[tuple[int, str]]:
        results = []
        for i, line in enumerate(self.lines):
            if re.search(pattern, line, flags):
                results.append((i + 1, line.rstrip()))
        return results

    def grep_context(self, pattern: str, before: int = 3, after: int = 10) -> list[str]:
        matches = []
        for i, line in enumerate(self.lines):
            if re.search(pattern, line):
                start = max(0, i - before)
                end = min(len(self.lines), i + after + 1)
                block = ''.join(self.lines[start:end])
                matches.append(block)
        return matches

    def get_section(self, start_line: int, end_line: int) -> str:
        return ''.join(self.lines[start_line - 1:end_line])

    # ------------------------------------------------------------------
    # Classification utilities
    # ------------------------------------------------------------------

    @staticmethod
    def classify_material(name: str) -> str:
        rules = [
            (['陶', '泥质', '灰陶', '红陶'], "陶器"),
            (['瓷', '白胎', '青花', '釉', '窑'], "瓷器"),
            (['铜', '青铜', '銅'], "青铜器"),
            (['铁', '鐵'], "铁器"),
            (['玉', '石', '玛瑙', '绿松石', '翡翠'], "玉石器"),
            (['骨', '角', '牙'], "骨角牙器"),
            (['漆', '木'], "漆木器"),
            (['金', '银'], "金银器"),
            (['钱', '币', '铢', '宝', '贝'], "货币"),
            (['料', '琉璃', '玻璃'], "料器"),
        ]
        for keywords, material in rules:
            if any(k in name for k in keywords):
                return material
        return "其他"

    @staticmethod
    def classify_vessel_type(name: str) -> str:
        types = {
            '罐': '罐', '壶': '壶', '瓶': '瓶', '盆': '盆', '碗': '碗',
            '盘': '盘', '杯': '杯', '尊': '尊', '罍': '罍', '瓮': '瓮',
            '鬲': '鬲', '豆': '豆', '簋': '簋', '爵': '爵', '斝': '斝',
            '觚': '觚', '鼎': '鼎', '洗': '洗', '炉': '炉', '灯': '灯',
            '枕': '枕', '碟': '碟', '盏': '盏', '缸': '缸', '盒': '盒',
            '戈': '戈', '矛': '矛', '剑': '剑', '刀': '刀', '镞': '镞',
            '戟': '戟', '弩机': '弩机',
            '斧': '斧', '锛': '锛', '凿': '凿', '铲': '铲', '锄': '锄',
            '镰': '镰', '纺轮': '纺轮', '锥': '锥',
            '璧': '璧', '琮': '琮', '璜': '璜', '玦': '玦', '环': '环',
            '串珠': '串珠', '珠': '串珠', '坠': '坠饰', '带钩': '带钩',
            '带扣': '带扣', '带饰': '带饰', '耳坠': '耳坠', '耳环': '耳环',
            '手镯': '手镯', '镯': '手镯', '簪': '簪', '钗': '簪',
            '扣': '扣饰', '铃': '铃', '鼓': '鼓', '磬': '磬',
            '印': '印章', '镜': '镜', '钱': '钱币', '币': '钱币',
            '俑': '俑', '案': '案', '台': '台',
        }
        for key, val in types.items():
            if key in name:
                return val
        return name

    @staticmethod
    def parse_num(s: str):
        if not s:
            return None
        s = s.strip()
        if '~' in s:
            parts = s.split('~')
            try:
                return round((float(parts[0]) + float(parts[1])) / 2, 2)
            except ValueError:
                return s
        try:
            return float(s)
        except ValueError:
            return s

    @staticmethod
    def extract_dimensions(text: str) -> dict:
        result = {"墓口长": None, "墓口宽": None, "墓深": None}

        # Combined pattern: 长2.7、宽2、深1.3米
        m = re.search(
            r'(?:南北)?长\s*([\d.]+)\s*[、，]\s*(?:东西)?宽\s*([\d.]+(?:~[\d.]+)?)\s*[、，]\s*(?:残)?深\s*([\d.]+(?:~[\d.]+)?)',
            text
        )
        if m:
            result["墓口长"] = WebTombParser.parse_num(m.group(1))
            result["墓口宽"] = WebTombParser.parse_num(m.group(2))
            result["墓深"] = WebTombParser.parse_num(m.group(3))
            return result

        # Fallback: try separate patterns
        m = re.search(r'(?:南北)?长\s*([\d.]+)', text)
        if m:
            result["墓口长"] = WebTombParser.parse_num(m.group(1))
        m = re.search(r'(?:东西)?宽\s*([\d.]+(?:~[\d.]+)?)', text)
        if m:
            result["墓口宽"] = WebTombParser.parse_num(m.group(1))
        m = re.search(r'(?:残)?深\s*([\d.]+(?:~[\d.]+)?)', text)
        if m:
            result["墓深"] = WebTombParser.parse_num(m.group(1))

        return result

    @staticmethod
    def extract_direction(text: str) -> str:
        for pattern in [
            r'方向\s*\$?\s*(\d+)\s*\^?\{?\\?circ\}?\s*\$?°?',
            r'方向\s*(\d+)°',
            r'方向\s*(南北向|东西向|南向|北向|东向|西向)',
        ]:
            m = re.search(pattern, text)
            if m:
                val = m.group(1)
                return f"{val}°" if val.isdigit() else val
        return ""

    # ------------------------------------------------------------------
    # Sorting
    # ------------------------------------------------------------------

    def sort_tombs(self):
        def key(t):
            id_str = t['墓葬编号']
            m = re.search(r'(\d+)$', id_str)
            if m:
                prefix = re.sub(r'\d+$', '', id_str) or 'Z'
                return (prefix, int(m.group(1)))
            return (id_str, 0)
        self.tombs.sort(key=key)

    # ------------------------------------------------------------------
    # Export methods (return strings/bytes, no file I/O)
    # ------------------------------------------------------------------

    def to_json(self) -> dict:
        self.sort_tombs()
        return {
            "墓葬列表": self.tombs,
            "原始文本片段": self.source_note or f"来源：{self.report_name}，共提取{len(self.tombs)}座墓葬"
        }

    def to_json_string(self) -> str:
        return json.dumps(self.to_json(), ensure_ascii=False, indent=2)

    def to_csv_string(self) -> str:
        self.sort_tombs()
        output = io.StringIO()
        headers = [
            "墓葬编号", "年代", "墓向", "墓葬形制", "墓口长", "墓口宽", "墓深",
            "发掘位置", "层位", "备注",
            "器物编号", "器物名称", "材质", "器型", "数量", "特征描述"
        ]
        w = csv.writer(output)
        w.writerow(headers)
        for t in self.tombs:
            base = [
                t.get(k, '') for k in [
                    '墓葬编号', '年代', '墓向', '墓葬形制',
                    '墓口长', '墓口宽', '墓深', '发掘位置', '层位', '备注'
                ]
            ]
            arts = t.get('随葬器物', [])
            if arts:
                for a in arts:
                    row = base + [a.get(k, '') for k in [
                        '器物编号', '器物名称', '材质', '器型', '数量', '特征描述'
                    ]]
                    w.writerow(row)
            else:
                w.writerow(base + [''] * 6)
        # Add BOM for Excel compatibility
        return '\ufeff' + output.getvalue()

    def to_markdown_string(self) -> str:
        self.sort_tombs()
        parts = []
        parts.append(f"# 墓葬数据 — {self.report_name}\n")
        parts.append(f"共提取 **{len(self.tombs)}** 条墓葬记录\n")

        parts.append("## 概览\n")
        parts.append("| 墓葬编号 | 年代 | 形制 | 尺寸(长×宽×深) | 随葬品数 |")
        parts.append("|----------|------|------|----------------|----------|")
        for t in self.tombs:
            dim = ""
            l = t.get('墓口长')
            w = t.get('墓口宽')
            d = t.get('墓深')
            if l or w:
                dim = f"{l or ''}×{w or ''}×{d or ''}m"
            parts.append(
                f"| {t['墓葬编号']} | {t.get('年代', '')} | "
                f"{t.get('墓葬形制', '')} | {dim} | "
                f"{len(t.get('随葬器物', []))} |"
            )

        parts.append("\n## 详细记录\n")
        for t in self.tombs:
            parts.append(f"### {t['墓葬编号']}\n")
            for label in ['年代', '墓向', '墓葬形制', '墓口长', '墓口宽',
                          '墓深', '发掘位置', '层位', '备注']:
                val = t.get(label, '')
                if val:
                    parts.append(f"- **{label}**: {val}")
            arts = t.get('随葬器物', [])
            if arts:
                parts.append(f"\n**随葬器物** ({len(arts)}件)\n")
                parts.append("| 编号 | 名称 | 材质 | 器型 | 数量 | 特征描述 |")
                parts.append("|------|------|------|------|------|----------|")
                for a in arts:
                    desc = a.get('特征描述', '')
                    if len(desc) > 80:
                        desc = desc[:80] + '...'
                    parts.append(
                        f"| {a.get('器物编号', '')} | {a.get('器物名称', '')} | "
                        f"{a.get('材质', '')} | {a.get('器型', '')} | "
                        f"{a.get('数量', '')} | {desc} |"
                    )
            parts.append("")

        return '\n'.join(parts)
