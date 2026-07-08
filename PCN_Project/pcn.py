import tkinter as tk
import math

# ── Layout constants ─────────────────────────────────────────────────────────
W, H = 1060, 540
NODE_POS = {
    'h1': (90,  275),
    's1': (265, 275),
    's2': (430, 140),
    's3': (595, 140),
    's4': (770, 275),
    's5': (512, 415),
    'h2': (950, 275),
}
NODE_TYPE = {n: ('host' if n.startswith('h') else 'switch') for n in NODE_POS}

# (node_a, node_b, eth_label_a_side, eth_label_b_side)
EDGES = [
    ('h1', 's1', 'eth1', 'eth1'),
    ('s1', 's2', 'eth2', 'eth1'),
    ('s1', 's5', 'eth3', 'eth1'),
    ('s2', 's3', 'eth2', 'eth1'),
    ('s3', 's4', 'eth2', 'eth2'),
    ('s5', 's4', 'eth2', 'eth3'),
    ('s4', 'h2', 'eth1', 'eth1'),
]

PATH_LOWER = ['h1', 's1', 's5', 's4', 'h2']    # original via s5
PATH_UPPER = ['h1', 's1', 's2', 's3', 's4', 'h2']  # rerouted after s5 down

HOST_R  = 30   # host circle radius
SW_HALF = 27   # half of switch square side


class NetworkGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PCN Network Visualization")
        self.root.resizable(False, False)
        self.root.configure(bg='#f0f2f5')

        self.s5_down      = False
        self.animating    = False
        self._packet_oval = None
        self._anim_after  = None

        self._build_ui()
        self.redraw()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        self.canvas = tk.Canvas(
            self.root, width=W, height=H,
            bg='white', highlightthickness=1, highlightbackground='#ccc'
        )
        self.canvas.pack(padx=14, pady=(14, 6))

        bar = tk.Frame(self.root, bg='#f0f2f5')
        bar.pack(fill=tk.X, padx=14, pady=(0, 14))

        self.s5_btn = tk.Button(
            bar, text='⬇  Bring s5 Down', width=17,
            command=self._toggle_s5,
            font=('Helvetica', 10, 'bold'),
            bg='#e74c3c', fg='white',
            activebackground='#c0392b', activeforeground='white',
            relief=tk.FLAT, padx=6, pady=5, cursor='hand2', bd=0
        )
        self.s5_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.send_btn = tk.Button(
            bar, text='▶  Send Packet', width=15,
            command=self._send_packet,
            font=('Helvetica', 10, 'bold'),
            bg='#2980b9', fg='white',
            activebackground='#1a6fa3', activeforeground='white',
            relief=tk.FLAT, padx=6, pady=5, cursor='hand2', bd=0
        )
        self.send_btn.pack(side=tk.LEFT, padx=(0, 14))

        self.status_var = tk.StringVar()
        tk.Label(
            bar, textvariable=self.status_var,
            font=('Helvetica', 10), bg='#f0f2f5', fg='#333'
        ).pack(side=tk.LEFT)

        self._refresh_controls()

    def _refresh_controls(self):
        if self.s5_down:
            self.s5_btn.config(text='⬆  Bring s5 Up',
                               bg='#27ae60', activebackground='#1e8449')
            path_str = 'h1 → s1 → s2 → s3 → s4 → h2'
            self.status_var.set(f'  s5 DOWN  |  rerouted: {path_str}')
        else:
            self.s5_btn.config(text='⬇  Bring s5 Down',
                               bg='#e74c3c', activebackground='#c0392b')
            path_str = 'h1 → s1 → s5 → s4 → h2'
            self.status_var.set(f'  s5 UP    |  active path: {path_str}')

    # ── Drawing ───────────────────────────────────────────────────────────────

    @property
    def _active_path(self):
        return PATH_UPPER if self.s5_down else PATH_LOWER

    def _active_edge_set(self):
        p = self._active_path
        return {(p[i], p[i+1]) for i in range(len(p)-1)} | \
               {(p[i+1], p[i]) for i in range(len(p)-1)}

    def redraw(self):
        self.canvas.delete('all')
        active = self._active_edge_set()
        self._draw_edges(active)
        self._draw_nodes()
        self._draw_legend()

    def _draw_edges(self, active):
        for n1, n2, lbl1, lbl2 in EDGES:
            x1, y1 = NODE_POS[n1]
            x2, y2 = NODE_POS[n2]
            s5_edge = 's5' in (n1, n2)
            is_act  = (n1, n2) in active

            if self.s5_down and s5_edge:
                color, width, dash = '#ffaaaa', 2, (6, 4)
            elif is_act:
                color, width, dash = '#27ae60', 3, ()
            else:
                color, width, dash = '#bbbbbb', 2, ()

            self.canvas.create_line(x1, y1, x2, y2,
                                    fill=color, width=width, dash=dash)

            # Perpendicular offset for eth labels
            dx, dy = x2 - x1, y2 - y1
            length = math.hypot(dx, dy) or 1
            px, py = -dy / length * 13, dx / length * 13

            lc = '#999' if (self.s5_down and s5_edge) else '#555'
            for t, lbl in ((0.22, lbl1), (0.78, lbl2)):
                lx = x1 + t * dx + px
                ly = y1 + t * dy + py
                self.canvas.create_text(lx, ly, text=lbl,
                                        font=('Helvetica', 8), fill=lc)

    def _draw_nodes(self):
        for name, (cx, cy) in NODE_POS.items():
            if NODE_TYPE[name] == 'host':
                self.canvas.create_oval(
                    cx - HOST_R, cy - HOST_R,
                    cx + HOST_R, cy + HOST_R,
                    fill='#d6eaf8', outline='#1a5276', width=2
                )
                self.canvas.create_text(cx, cy, text=name,
                                        font=('Helvetica', 13, 'bold'),
                                        fill='#1a5276')
            else:
                is_down = self.s5_down and name == 's5'
                fill    = '#ffd5d5' if is_down else '#ffffff'
                border  = '#c0392b' if is_down else '#2c3e50'
                bw      = 2.5      if is_down else 2
                self.canvas.create_rectangle(
                    cx - SW_HALF, cy - SW_HALF,
                    cx + SW_HALF, cy + SW_HALF,
                    fill=fill, outline=border, width=bw
                )
                txt_color = '#c0392b' if is_down else '#2c3e50'
                self.canvas.create_text(cx, cy - (6 if is_down else 0),
                                        text=name,
                                        font=('Helvetica', 13, 'bold'),
                                        fill=txt_color)
                if is_down:
                    self.canvas.create_text(cx, cy + 9,
                                            text='✖ DOWN',
                                            font=('Helvetica', 7, 'bold'),
                                            fill='#c0392b')

    def _draw_legend(self):
        items = [
            ('#27ae60', '─── Active path'),
            ('#bbbbbb', '─── Inactive link'),
            ('#ffaaaa', '╌╌╌ Disabled link (s5)'),
            ('#ff6600', '● Packet'),
        ]
        x, y = 14, H - 22
        for color, label in items:
            self.canvas.create_text(x, y, text=label, anchor='w',
                                    font=('Helvetica', 8), fill=color)
            x += 155

    # ── Controls ──────────────────────────────────────────────────────────────

    def _toggle_s5(self):
        if self.animating:
            return
        self.s5_down = not self.s5_down
        self.redraw()
        self._refresh_controls()

    def _send_packet(self):
        if self.animating:
            return
        self.animating = True
        self.send_btn.config(state=tk.DISABLED)
        waypoints = [NODE_POS[n] for n in self._active_path]
        self._animate(waypoints, seg=0, t=0.0)

    # ── Animation ─────────────────────────────────────────────────────────────

    def _animate(self, waypoints, seg, t):
        if seg >= len(waypoints) - 1:
            if self._packet_oval:
                self.canvas.delete(self._packet_oval)
                self._packet_oval = None
            self.animating = False
            self.send_btn.config(state=tk.NORMAL)
            return

        x1, y1 = waypoints[seg]
        x2, y2 = waypoints[seg + 1]
        px = x1 + t * (x2 - x1)
        py = y1 + t * (y2 - y1)

        R = 9
        if self._packet_oval:
            self.canvas.delete(self._packet_oval)
        self._packet_oval = self.canvas.create_oval(
            px - R, py - R, px + R, py + R,
            fill='#ff6600', outline='#c0392b', width=2
        )
        self.canvas.tag_raise(self._packet_oval)

        STEP = 0.04
        t_next = t + STEP
        if t_next >= 1.0:
            self._anim_after = self.root.after(
                20, self._animate, waypoints, seg + 1, 0.0)
        else:
            self._anim_after = self.root.after(
                20, self._animate, waypoints, seg, t_next)


def main():
    root = tk.Tk()
    NetworkGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
