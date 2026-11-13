"""Native macOS menu bar item. All AppKit updates run on the main thread."""

import logging
import threading
from datetime import datetime

import objc
from AppKit import (
    NSApp,
    NSColor,
    NSFont,
    NSImage,
    NSMakeRect,
    NSMakeSize,
    NSMenu,
    NSMenuItem,
    NSObject,
    NSPasteboard,
    NSPasteboardTypeString,
    NSStatusBar,
    NSTextField,
    NSVariableStatusItemLength,
    NSView,
)
from Foundation import NSRunLoop, NSRunLoopCommonModes, NSTimer
from PyObjCTools import AppHelper

from ccask.menubar import monitor_snapshot
from ccask.sdk_info import install_command


def compact(value):
    if value is None:
        return "—"
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1000:
        return f"{value / 1000:.1f}K"
    return str(value)


def cells(row):
    return (
        f'{row["requests"]:,}',
        f'{row["total_tokens"]:,}' if row["total_tokens"] is not None else "—",
        f'${float(row["cost"]):.4f}' if row["cost"] is not None else "—",
        f'{row["success_rate"]:.1%}' if row["success_rate"] is not None else "—",
    )


def statistics_view(snapshot):
    rows = snapshot["rows"] or [{"label": "全部项目", **snapshot["summary"]}]
    visible = rows[:10]
    height = 108 + 26 * (len(visible) + 2) + (22 if len(rows) > 10 else 0)
    view = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, 600, height))

    def label(text, x, top, width, size=12, bold=False, muted=False):
        field = NSTextField.labelWithString_(text)
        field.setFrame_(NSMakeRect(x, height - top - 20, width, 20))
        font = NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size)
        field.setFont_(font)
        field.setTextColor_(NSColor.secondaryLabelColor() if muted else NSColor.labelColor())
        field.setLineBreakMode_(4)  # NSLineBreakByTruncatingTail
        field.setToolTip_(text)
        view.addSubview_(field)

    label(f'{snapshot["period_label"]} · {snapshot["scope"]}', 18, 10, 560, 13, True)
    summary = snapshot["summary"]
    values = cells(summary)
    for i, (name, value) in enumerate(zip(("调用次数", "Token 用量", "估算费用（美元）", "成功率"), values)):
        label(name, 18 + i * 144, 38, 140, 10, muted=True)
        label(value, 18 + i * 144, 57, 140, 16, True)
    xs, widths = (18, 220, 288, 398, 508), (196, 62, 104, 104, 74)
    for text, x, width in zip(("项目", "调用", "Token", "费用（$）", "成功率"), xs, widths):
        label(text, x, 88, width, 10, muted=True)
    for i, row in enumerate(visible + [{"label": "合计", **summary}]):
        for text, x, width in zip((row["label"], *cells(row)), xs, widths):
            label(text, x, 112 + i * 26, width, 11, i == len(visible))
    footer = (
        snapshot["sync_error"] or
        ("同步于 " + datetime.fromtimestamp(snapshot["last_sync"]).strftime("%H:%M:%S")
         if snapshot["last_sync"] else "正在同步用量…")
    )
    if len(rows) > 10:
        footer = f"共 {len(rows)} 个项目，表格显示前 10 个 · " + footer
    label(footer, 18, height - 25, 566, 10, muted=True)
    return view


class MenuBarController(NSObject):
    def initWithContext_(self, context):
        self = objc.super(MenuBarController, self).init()  # noqa: PLW0642 - PyObjC initializer
        if self is None:
            return None
        self.window, self.settings, self.db, self.usage = context
        self.busy = False
        self.stopped = False
        self.item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_("chart.bar", "CC Ask 用量")
        if image:
            image.setSize_(NSMakeSize(18, 18))
            image.setTemplate_(True)
            self.item.button().setImage_(image)
        self.item.button().setTitle_(" —")
        self.item.button().setToolTip_("CC Ask · 用量监控")
        self.menu = NSMenu.alloc().initWithTitle_("CC Ask")
        self.menu.setAutoenablesItems_(False)
        self.menu.setDelegate_(self)
        self.table = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("正在读取用量…", None, "")
        self.table.setEnabled_(False)
        self.menu.addItem_(self.table)
        self.menu.addItem_(NSMenuItem.separatorItem())
        for title, action in (
            ("打开主窗口", "showMain:"),
            ("监控设置…", "showSettings:"),
            ("复制 Python 安装命令", "copyInstall:"),
            ("隐藏主窗口", "hideWindow:"),
        ):
            item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, "")
            item.setTarget_(self)
            self.menu.addItem_(item)
        self.menu.addItem_(NSMenuItem.separatorItem())
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("退出 CC Ask", "quit:", "")
        quit_item.setTarget_(self)
        self.menu.addItem_(quit_item)
        self.item.setMenu_(self.menu)
        self.timer = NSTimer.timerWithTimeInterval_target_selector_userInfo_repeats_(
            5, self, "refresh:", None, True
        )
        NSRunLoop.mainRunLoop().addTimer_forMode_(self.timer, NSRunLoopCommonModes)
        self.refresh_(None)
        return self

    def menuWillOpen_(self, menu):
        self.refresh_(None)

    def refresh_(self, sender):
        if self.busy or self.stopped:
            return
        self.busy = True

        def worker():
            try:
                snapshot = monitor_snapshot(self.settings, self.db, self.usage)
            except Exception:  # noqa: BLE001 - keep the native menu usable after refresh failure
                logging.getLogger("ccask.desktop").warning("menubar_refresh_failed")
                snapshot = None
            AppHelper.callAfter(self.applySnapshot_, snapshot)

        threading.Thread(target=worker, daemon=True).start()

    def applySnapshot_(self, snapshot):
        self.busy = False
        if self.stopped:
            return
        if snapshot is None:
            self.item.button().setTitle_(" !")
            self.item.button().setToolTip_("CC Ask · 用量暂时无法读取，请打开主窗口检查")
            return
        self.table.setView_(statistics_view(snapshot))
        self.item.button().setTitle_(" " + compact(snapshot["summary"]["total_tokens"]))
        self.item.button().setToolTip_(
            f'CC Ask · {snapshot["period_label"]} · {snapshot["scope"]} · Token 用量'
        )

    def showMain_(self, sender):
        self.window.restore()
        self.window.show()
        NSApp.activateIgnoringOtherApps_(True)

    def showSettings_(self, sender):
        self.showMain_(sender)
        threading.Thread(
            target=self.window.evaluate_js,
            args=("location.hash = '#/settings'",),
            daemon=True,
        ).start()

    def copyInstall_(self, sender):
        pasteboard = NSPasteboard.generalPasteboard()
        pasteboard.clearContents()
        pasteboard.setString_forType_(install_command(), NSPasteboardTypeString)

    def hideWindow_(self, sender):
        self.window.hide()

    def quit_(self, sender):
        self.window.destroy()

    @objc.python_method
    def stop(self):
        self.stopped = True
        self.timer.invalidate()
        NSStatusBar.systemStatusBar().removeStatusItem_(self.item)
