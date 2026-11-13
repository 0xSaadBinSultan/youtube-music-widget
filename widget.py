#!/usr/bin/env python3
"""An Android-style controller for the standalone background music client."""
import colorsys
import fcntl
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time

import gi
gi.require_version('Gtk','3.0')
gi.require_version('GdkPixbuf','2.0')
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib, Pango
from mpris import MusicMedia, read_artwork
from player import open_player

STATE = Path.home()/'.config/laptop-music/position.json'
CSS = b'''
window { background-color: transparent; }
.music { background-color: #80443d; border: none; border-radius: 2px; padding: 0; }
.track { color: #fff5ef; font-family: "DejaVu Sans"; font-size: 12px; }
button { color: #fff8ef; background: transparent; background-image: none; box-shadow: none;
 text-shadow: none; border: none; border-radius: 4px; padding: 0; min-width: 0; min-height: 0; }
button:hover { background-color: rgba(255,255,255,0.12); }
button:disabled { opacity: 0.4; }
menu.music-menu { background-color: #191f2b; background-image: none; border: 1px solid #46516a; padding: 5px; }
menu.music-menu menuitem { background: transparent; color: #edf0f7; padding: 9px 14px; }
menu.music-menu menuitem label { color: #edf0f7; }
menu.music-menu menuitem:hover { background-color: #344462; }
'''

def read_state():
    try:return json.loads(STATE.read_text())
    except (OSError,ValueError):return {}

def save_state(data):
    STATE.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,name=tempfile.mkstemp(dir=STATE.parent,prefix='.position-')
    with os.fdopen(fd,'w') as out:json.dump(data,out)
    Path(name).replace(STATE)

class MusicWidget(Gtk.Window):
    def __init__(self, media=None, connect=True):
        super().__init__(title='YouTube Music Widget')
        self.media=media or MusicMedia();self.current={'connected':False}
        self.polling=False;self.drag=None;self.art_key=None;self.pixbuf=None;self.opening_until=0
        self.set_decorated(False);self.set_resizable(False)
        self.set_type_hint(Gdk.WindowTypeHint.DESKTOP);self.set_keep_below(True)
        self.set_skip_taskbar_hint(True);self.set_skip_pager_hint(True);self.set_accept_focus(False)
        self.set_app_paintable(True)
        visual=self.get_screen().get_rgba_visual()
        if visual:self.set_visual(visual)
        provider=Gtk.CssProvider();provider.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_screen(self.get_screen(),provider,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self.connect('draw',self.clear);self.connect('destroy',Gtk.main_quit)
        self.panel=Gtk.Box(spacing=0);self.panel.get_style_context().add_class('music')
        self.add(self.panel);self.set_size_request(480,80)
        self.palette=Gtk.CssProvider()
        self.panel.get_style_context().add_provider(self.palette,Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION+1)
        self.cover=Gtk.DrawingArea();self.cover.set_size_request(80,80);self.cover.connect('draw',self.draw_cover)
        self.panel.pack_start(self.grip(self.cover),False,False,0)
        body=Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=1)
        body.set_margin_start(12);body.set_margin_end(10);body.set_margin_top(7);body.set_margin_bottom(5)
        self.panel.pack_start(body,True,True,0)
        self.title=Gtk.Label(xalign=0);self.title.get_style_context().add_class('track')
        self.title.set_ellipsize(Pango.EllipsizeMode.END);self.title.set_max_width_chars(43)
        self.title.set_size_request(-1,23)
        body.pack_start(self.grip(self.title),False,False,0)
        controls=Gtk.Box(homogeneous=True,spacing=4)
        self.dislike=self.button('dislike','Rate songs in the YouTube Music player',lambda:None)
        self.previous=self.button('previous','Previous track',lambda:self.action('Previous'))
        self.play=self.button('play','Play / pause',lambda:self.action('PlayPause'))
        self.next=self.button('next','Next track',lambda:self.action('Next'))
        self.like=self.button('like','Rate songs in the YouTube Music player',lambda:None)
        for button in (self.dislike,self.previous,self.play,self.next,self.like):
            controls.pack_start(button,True,True,0)
        self.dislike.set_sensitive(False);self.like.set_sensitive(False)
        body.pack_start(controls,True,True,0)
        self.render({'connected':False});self.show_all();GLib.idle_add(self.place)
        if connect:GLib.timeout_add_seconds(2,self.poll);self.poll()

    def grip(self,child):
        grip=Gtk.EventBox();grip.set_visible_window(False);grip.add(child)
        grip.add_events(Gdk.EventMask.BUTTON_PRESS_MASK|Gdk.EventMask.BUTTON_RELEASE_MASK|Gdk.EventMask.POINTER_MOTION_MASK)
        grip.connect('button-press-event',self.drag_start);grip.connect('motion-notify-event',self.drag_move)
        grip.connect('button-release-event',self.drag_end)
        grip.set_tooltip_text('Drag to move · Right-click for menu')
        return grip

    def button(self,icon,tooltip,callback):
        button=Gtk.Button();button.set_focus_on_click(False);button.set_tooltip_text(tooltip)
        picture=Gtk.DrawingArea();picture.set_size_request(24,24)
        picture.set_halign(Gtk.Align.CENTER);picture.set_valign(Gtk.Align.CENTER)
        picture.connect('draw',self.draw_icon,icon);button.add(picture)
        button.connect('clicked',lambda _:callback());return button

    def draw_icon(self,_area,cr,icon):
        cr.set_source_rgba(1,.97,.93,1);cr.set_line_width(1.8);cr.set_line_join(1);cr.set_line_cap(1)
        if icon=='play':
            if self.current.get('status')=='Playing':
                cr.rectangle(6,4,4,16);cr.rectangle(14,4,4,16);cr.fill()
            else:cr.move_to(7,3);cr.line_to(21,12);cr.line_to(7,21);cr.close_path();cr.fill()
        elif icon in ('previous','next'):
            if icon=='next':cr.translate(24,0);cr.scale(-1,1)
            cr.rectangle(4,4,3,16);cr.fill()
            cr.move_to(19,4);cr.line_to(8,12);cr.line_to(19,20);cr.close_path();cr.fill()
        else:
            if icon=='dislike':cr.translate(24,24);cr.rotate(math.pi)
            cr.rectangle(3,10,4,11);cr.stroke()
            for index,(x,y) in enumerate([(10,21),(10,10),(13,3),(15,3),(16,5),(15,10),(21,10),(22,12),(19,21)]):
                cr.move_to(x,y) if index==0 else cr.line_to(x,y)
            cr.close_path();cr.stroke()
        return False

    def clear(self,_widget,cr):
        import cairo
        cr.set_operator(cairo.OPERATOR_SOURCE);cr.set_source_rgba(0,0,0,0);cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER);return False

    def draw_cover(self,area,cr):
        width,height=area.get_allocated_width(),area.get_allocated_height()
        cr.rectangle(0,0,width,height);cr.clip();cr.set_source_rgb(.37,.23,.23);cr.paint()
        if self.pixbuf:
            scale=max(width/self.pixbuf.get_width(),height/self.pixbuf.get_height())
            cr.translate((width-self.pixbuf.get_width()*scale)/2,(height-self.pixbuf.get_height()*scale)/2)
            cr.scale(scale,scale);Gdk.cairo_set_source_pixbuf(cr,self.pixbuf,0,0);cr.paint()
        else:
            cr.set_source_rgba(1,.91,.84,.7);cr.select_font_face('DejaVu Sans');cr.set_font_size(42)
            cr.move_to(24,58);cr.show_text('♪')
        return False

    def poll(self):
        if self.polling:return True
        self.polling=True
        def work():
            try:state=self.media.poll()
            except Exception:state={'connected':False}
            GLib.idle_add(self.render,state)
        threading.Thread(target=work,daemon=True).start();return True

    def render(self,state):
        self.polling=False;self.current=state
        connected=state.get('connected',False)
        title=state.get('title','YouTube Music — click play to open')
        artist=state.get('artist','')
        self.title.set_text(title+(' — '+artist if artist else ''))
        self.title.set_tooltip_text(self.title.get_text()+'\nDrag to move · Right-click for menu')
        self.play.set_sensitive(not state.get('ready') or state.get('can_play',False))
        self.play.set_tooltip_text('Play / pause YouTube Music' if state.get('ready') else 'Open the standalone music player')
        self.play.get_child().queue_draw()
        self.previous.set_sensitive(connected and state.get('can_previous',False))
        self.next.set_sensitive(connected and state.get('can_next',False))
        key=state.get('art','')
        if key!=self.art_key:
            self.art_key=key;self.pixbuf=None;self.cover.queue_draw();self.palette.load_from_data(b'.music { background-color: #80443d; }')
            if key:
                def load():
                    try:
                        raw=read_artwork(key);loader=GdkPixbuf.PixbufLoader()
                        loader.set_size(128,128);loader.write(raw);loader.close()
                        GLib.idle_add(self.set_cover,key,loader.get_pixbuf())
                    except Exception:pass
                threading.Thread(target=load,daemon=True).start()
        return False

    def set_cover(self,key,pixbuf):
        if key!=self.art_key:return False
        self.pixbuf=pixbuf;self.cover.queue_draw()
        sample=pixbuf.scale_simple(12,12,GdkPixbuf.InterpType.BILINEAR)
        pixels=sample.get_pixels();stride=sample.get_rowstride();channels=sample.get_n_channels()
        rgb=[sum(pixels[y*stride+x*channels+c] for y in range(12) for x in range(12))/144/255 for c in range(3)]
        hue,saturation,value=colorsys.rgb_to_hsv(*rgb)
        color=colorsys.hsv_to_rgb(hue,max(.25,min(.65,saturation)),max(.27,min(.46,value*.72)))
        values=','.join(str(round(component*255)) for component in color)
        self.palette.load_from_data(('.music { background-color: rgb('+values+'); }').encode())
        return False

    def action(self,method):
        if not self.current.get('connected') or not self.current.get('ready'):
            if method=='PlayPause':self.open_music()
            return
        if not self.media.command(method,callback=lambda success:self.poll()):self.poll()

    def place(self,position=None):
        display=self.get_display();monitor=display.get_primary_monitor() or display.get_monitor(0)
        rect=monitor.get_geometry();width,height=self.get_size()
        saved=read_state() if position is None else position
        default=(rect.x+(rect.width-width)//2,rect.y+max(50,rect.height-height-100))
        x,y=int(saved.get('x',default[0])),int(saved.get('y',default[1]))
        screens=[display.get_monitor(i).get_geometry() for i in range(display.get_n_monitors())]
        if not any(x<r.x+r.width and x+width>r.x and y<r.y+r.height and y+height>r.y for r in screens):x,y=default
        self.move(x,y);return False

    def save_position(self,preferred=False):
        x,y=self.get_position();saved=read_state();saved.update(x=x,y=y)
        if preferred:saved['preferred_position']={'x':x,'y':y}
        save_state(saved);return False

    def reset_position(self):
        self.place(read_state().get('preferred_position',{}));GLib.timeout_add(150,self.save_position)

    def drag_start(self,_widget,event):
        if event.button==3:self.menu(event);return True
        if event.button==1:self.drag=(event.x_root,event.y_root,self.get_position())
        return True

    def drag_move(self,_widget,event):
        if self.drag:
            x,y,(old_x,old_y)=self.drag;self.move(int(old_x+event.x_root-x),int(old_y+event.y_root-y))
        return True

    def drag_end(self,*_args):
        if self.drag:self.drag=None;GLib.timeout_add(150,self.save_position)
        return True

    def open_music(self):
        if time.monotonic()<self.opening_until:return
        try:open_player();self.opening_until=time.monotonic()+10
        except (OSError,RuntimeError,subprocess.SubprocessError):
            self.title.set_text('Unable to open player — use the application launcher')

    def menu(self,event=None):
        menu=Gtk.Menu();menu.get_style_context().add_class('music-menu')
        for title,callback in [('Open YouTube Music player',self.open_music),
                               ('Set position',lambda:self.save_position(True)),
                               ('Reset position',self.reset_position),('Quit widget',Gtk.main_quit)]:
            item=Gtk.MenuItem(label=title);item.connect('activate',lambda _,fn=callback:fn());menu.append(item)
        menu.show_all();menu.popup_at_pointer(event)

if __name__=='__main__':
    lock=(Path(os.environ.get('XDG_RUNTIME_DIR','/tmp'))/'laptop-music.lock').open('a+')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit(0)
    MusicWidget();Gtk.main()
