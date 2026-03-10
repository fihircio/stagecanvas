import mido
import time
import asyncio
from typing import Callable, Any
import threading

class MIDIHandler:
    def __init__(self, port_name: str | None = None, trigger_callback: Callable[[dict[str, Any]], None] = None, cc_callback: Callable[[int, int], None] = None):
        self.port_name = port_name
        self.trigger_callback = trigger_callback
        self.cc_callback = cc_callback
        self.inport = None
        self._thread = None
        self._running = False
        self._loop = None

    def _open_port(self):
        try:
            inputs = mido.get_input_names()
            if not inputs:
                print("[midi-handler] No MIDI input ports found.")
                return False
            
            target_port = self.port_name
            if target_port is None or target_port not in inputs:
                target_port = inputs[0] # Just take the first one if not specified or not found
                
            self.inport = mido.open_input(target_port)
            print(f"[midi-handler] Connected to MIDI port: {target_port}")
            return True
        except Exception as e:
            print(f"[midi-handler] Failed to open MIDI port: {e}")
            return False

    def start(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop
        if not self._open_port():
            return

        self._running = True
        self._thread = threading.Thread(target=self._midi_worker, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self.inport:
            self.inport.close()
        if self._thread:
            self._thread.join(timeout=1.0)
        print("[midi-handler] Stopped.")

    def _midi_worker(self):
        try:
            for msg in self.inport:
                if not self._running:
                    break
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    self._handle_note_on(msg.note, msg.velocity)
                elif msg.type == 'control_change':
                    self._handle_cc(msg.control, msg.value)
        except Exception as e:
            print(f"[midi-handler] Worker error: {e}")

    def _handle_note_on(self, note: int, velocity: int):
        if not self.trigger_callback:
            return
            
        payload = {
            "rule_id": f"midi-note-{note}",
            "payload": {
                "velocity": velocity,
                "source": "midi",
                "timestamp": time.time()
            }
        }
        
        if asyncio.iscoroutinefunction(self.trigger_callback):
            asyncio.run_coroutine_threadsafe(self.trigger_callback(payload), self._loop)
        else:
            self._loop.call_soon_threadsafe(self.trigger_callback, payload)

    def _handle_cc(self, control: int, value: int):
        if not self.cc_callback:
            return
            
        if asyncio.iscoroutinefunction(self.cc_callback):
            asyncio.run_coroutine_threadsafe(self.cc_callback(control, value), self._loop)
        else:
            self._loop.call_soon_threadsafe(self.cc_callback, control, value)
