// SPDX-License-Identifier: GPL-3.0-or-later
// Nebulix Dock Zoom: macOS-style magnification on top of the Ubuntu Dock (ubuntu-dock@ubuntu.com).
// It only touches transform properties (scale/translation) of the dock icons and restores them on disable.
// Factor comes from ~/.config/nebulix/dock-zoom.json ({"factor": 1.6}) and is reloaded live.
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

const DOCK_UUID = 'ubuntu-dock@ubuntu.com';
const FRAME_MS = 16;
const TAU_MS = 55;          // easing time constant
const RADIUS_ITEMS = 2.6;   // influence radius in icon slots
const DEFAULT_FACTOR = 1.6;

function loadFactor() {
    try {
        const path = GLib.build_filenamev([GLib.get_user_config_dir(), 'nebulix', 'dock-zoom.json']);
        const [ok, bytes] = GLib.file_get_contents(path);
        if (ok) {
            const f = Number(JSON.parse(new TextDecoder().decode(bytes)).factor);
            if (Number.isFinite(f))
                return Math.min(2.2, Math.max(1.1, f));
        }
    } catch (_e) { /* use default */ }
    return DEFAULT_FACTOR;
}

// One instance per dock window.
class DockZoom {
    constructor(dock, getFactor) {
        this._dock = dock;
        this._getFactor = getFactor;
        this._state = new Map();   // item -> current scale
        this._tick = 0;
        this._last = 0;
        this._hover = false;
        const box = dock._box;
        this._dead = false;
        this._destroyId = dock.connect('destroy', () => {
            this._dead = true;
            this._destroyId = 0;
            this.destroy();
        });
        const dashBox = dock.dash?._box;
        this._ids = [
            ...(dashBox ? [[dashBox, dashBox.connect('child-added', () => this._releaseAll())],
                           [dashBox, dashBox.connect('child-removed', () => this._releaseAll())]] : []),
            [box, box.connect('notify::hover', () => this._onHover())],
            [box, box.connect('motion-event', () => { this._onHover(); return Clutter.EVENT_PROPAGATE; })],
        ];
        // Magnified icons are drawn as clones on an overlay above the dock: the dock and its scroll
        // view clip everything that leaves their allocation, so scaling the real icons is not an option.
        this._overlay = null;
        this._clones = new Map();
        this._themeId = St.ThemeContext.get_for_stage(global.stage).connect('changed', () => this._releaseAll());
    }

    _items() {
        const box = this._dock.dash?._box;
        if (!box)
            return [];
        return box.get_children().filter(a => a.child && a.visible && a.mapped);
    }

    _onHover() {
        this._hover = this._dock._box.hover;
        this._start();
    }

    _start() {
        if (this._tick)
            return;
        this._last = GLib.get_monotonic_time();
        this._tick = GLib.timeout_add(GLib.PRIORITY_DEFAULT, FRAME_MS, () => this._step());
    }

    _step() {
        try {
            return this._doStep();
        } catch (e) {
            // never leave an icon hidden behind a clone: drop everything and stop animating
            logError(e, 'nebulix-dock-zoom: step failed');
            this._tick = 0;
            this._releaseAll();
            return GLib.SOURCE_REMOVE;
        }
    }

    _doStep() {
        const now = GLib.get_monotonic_time();
        const dt = Math.min(100, (now - this._last) / 1000);
        this._last = now;
        const k = 1 - Math.exp(-dt / TAU_MS);
        const items = this._items();
        const side = this._dock._position;
        const horizontal = side === St.Side.BOTTOM || side === St.Side.TOP;
        const [px, py] = global.get_pointer();
        const pointer = horizontal ? px : py;
        const factor = this._getFactor();
        const centers = [], sizes = [];
        for (const it of items) {
            const [x, y] = it.get_transformed_position();
            // item (the slot) is never scaled, only its child, so its geometry is stable
            sizes.push(horizontal ? it.width : it.height);
            centers.push((horizontal ? x : y) + sizes[sizes.length - 1] / 2);
        }
        let settled = true;
        const scales = items.map((it, i) => {
            const target = this._hover
                ? 1 + (factor - 1) * this._bump(Math.abs(pointer - centers[i]) / (sizes[i] || 1))
                : 1;
            const cur = this._state.get(it) ?? 1;
            const nxt = cur + (target - cur) * k;
            if (Math.abs(nxt - target) > 0.002)
                settled = false;
            return Math.abs(nxt - target) <= 0.002 ? target : nxt;
        });
        // push neighbours apart so scaled icons do not overlap, keeping the row centred
        const extra = scales.map((s, i) => (s - 1) * sizes[i]);
        const total = extra.reduce((a, b) => a + b, 0);
        let acc = 0;
        items.forEach((it, i) => {
            const shift = acc + extra[i] / 2 - total / 2;
            acc += extra[i];
            this._state.set(it, scales[i]);
            this._apply(it, scales[i], shift, side);
        });
        for (const it of [...this._state.keys()]) {
            if (!items.includes(it)) {
                this._state.delete(it);
                this._release(it);
            }
        }
        if (settled && !this._hover) {
            this._tick = 0;
            return GLib.SOURCE_REMOVE;
        }
        return GLib.SOURCE_CONTINUE;
    }

    _bump(d) {
        return d >= RADIUS_ITEMS ? 0 : 0.5 * (1 + Math.cos(Math.PI * d / RADIUS_ITEMS));
    }

    _cloneFor(item) {
        let c = this._clones.get(item);
        if (c)
            return c;
        if (!this._overlay) {
            this._overlay = new Clutter.Actor({reactive: false});
            Main.uiGroup.add_child(this._overlay);
        }
        const src = item.child;
        const [x, y] = src.get_transformed_position();
        c = new Clutter.Clone({source: src, reactive: false});
        c.set_position(x, y);
        c.set_size(src.width, src.height);
        this._overlay.add_child(c);
        src.opacity = 0;
        // if the real icon (or the clone) is destroyed from outside, never leave the other one hidden
        c._nbxSrc = src;
        c._nbxSrcId = src.connect('destroy', () => { c._nbxSrcId = 0; this._release(item); });
        this._clones.set(item, c);
        return c;
    }

    _apply(item, scale, shift, side) {
        if (scale === 1 && shift === 0) {
            this._release(item);
            return;
        }
        const c = this._cloneFor(item);
        const [x, y] = item.child.get_transformed_position();
        c.set_position(x, y);
        const horizontal = side === St.Side.BOTTOM || side === St.Side.TOP;
        c.set_pivot_point(side === St.Side.LEFT ? 0 : side === St.Side.RIGHT ? 1 : 0.5,
            side === St.Side.BOTTOM ? 1 : side === St.Side.TOP ? 0 : 0.5);
        c.set_scale(scale, scale);
        c.translation_x = horizontal ? shift : 0;
        c.translation_y = horizontal ? 0 : shift;
        // keep the hover label clear of the magnified icon
        const lab = item.label;
        if (lab && !this._dead) {
            const out = (scale - 1) * (horizontal ? item.child.height : item.child.width);
            lab.translation_x = side === St.Side.LEFT ? out : side === St.Side.RIGHT ? -out : 0;
            lab.translation_y = side === St.Side.BOTTOM ? -out : side === St.Side.TOP ? out : 0;
        }
    }

    _release(item) {
        const c = this._clones.get(item);
        this._clones.delete(item);
        if (c) {
            const src = c._nbxSrc;
            try {
                if (src && c._nbxSrcId)
                    src.disconnect(c._nbxSrcId);
            } catch (_e) { /* source already destroyed */ }
            try {
                if (src)
                    src.opacity = 255;
            } catch (_e) { /* source already destroyed */ }
            try {
                c.destroy();
            } catch (_e) { /* already gone with the dock */ }
        }
        if (!this._dead) {
            try {
                if (item.child)
                    item.child.opacity = 255;
                if (item.label) {
                    item.label.translation_x = 0;
                    item.label.translation_y = 0;
                }
            } catch (_e) { /* item disposed while the theme reloaded */ }
        }
        if (this._clones.size === 0 && this._overlay) {
            try {
                this._overlay.destroy();
            } catch (_e) { /* ignore */ }
            this._overlay = null;
        }
    }

    _releaseAll() {
        for (const it of [...this._clones.keys()])
            this._release(it);
        this._state.clear();
        if (this._dead)
            return;
        // belt and braces: every icon the dash currently holds must be visible
        try {
            for (const it of this._items()) {
                if (it.child && it.child.opacity !== 255)
                    it.child.opacity = 255;
            }
        } catch (_e) { /* dash disposed while the theme reloaded */ }
    }

    destroy() {
        if (this._gone)
            return;
        this._gone = true;
        if (this._tick)
            GLib.source_remove(this._tick);
        this._tick = 0;
        if (this._themeId) {
            St.ThemeContext.get_for_stage(global.stage).disconnect(this._themeId);
            this._themeId = 0;
        }
        if (!this._dead) {
            for (const [obj, id] of this._ids)
                obj.disconnect(id);
            if (this._destroyId)
                this._dock.disconnect(this._destroyId);
        }
        this._releaseAll();
    }
}

export default class NebulixDockZoom extends Extension {
    enable() {
        this._factor = loadFactor();
        this._zooms = new Map();
        const dir = Gio.File.new_for_path(GLib.build_filenamev([GLib.get_user_config_dir(), 'nebulix']));
        try {
            this._mon = dir.monitor_directory(Gio.FileMonitorFlags.NONE, null);
            this._monId = this._mon.connect('changed', () => { this._factor = loadFactor(); });
        } catch (_e) { /* config dir missing: default factor */ }
        this._extId = Main.extensionManager.connect('extension-state-changed', () => this._sync());
        // The dock may be created after us (or recreated on monitor changes)
        this._poll = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 2, () => { this._sync(); return GLib.SOURCE_CONTINUE; });
        this._sync();
    }

    async _docks() {
        const ext = Main.extensionManager.lookup(DOCK_UUID);
        if (!ext || ext.state !== 1 /* ENABLED */)
            return [];
        try {
            // the dock exports its manager from extension.js "so it can be accessed by other extensions"
            const mod = await import(`file://${ext.path}/extension.js`);
            return mod.dockManager?._allDocks ?? [];
        } catch (e) {
            logError(e, 'nebulix-dock-zoom: cannot reach the Ubuntu Dock');
            return [];
        }
    }

    async _sync() {
        const docks = await this._docks();
        if (!this._zooms)
            return;
        for (const [d, z] of [...this._zooms]) {
            if (!docks.includes(d)) {
                z.destroy();
                this._zooms.delete(d);
            }
        }
        for (const d of docks) {
            if (!this._zooms.has(d) && d._box && d.dash)
                this._zooms.set(d, new DockZoom(d, () => this._factor));
        }
        // self-heal: an idle dock never has hidden icons
        for (const z of this._zooms.values()) {
            if (!z._tick && z._clones.size === 0)
                z._releaseAll();
        }
    }

    disable() {
        if (this._poll)
            GLib.source_remove(this._poll);
        this._poll = 0;
        Main.extensionManager.disconnect(this._extId);
        if (this._mon) {
            this._mon.disconnect(this._monId);
            this._mon.cancel();
            this._mon = null;
        }
        for (const z of this._zooms.values())
            z.destroy();
        this._zooms = null;
    }
}
