import asyncio
import unittest
from unittest.mock import MagicMock, patch
import mido
from app.io.midi_handler import MIDIHandler

class TestMIDIHandler(unittest.IsolatedAsyncioTestCase):
    @patch('mido.get_input_names')
    @patch('mido.open_input')
    async def test_midi_callbacks(self, mock_open_input, mock_get_input_names):
        mock_get_input_names.return_value = ['Mock MIDI Device']
        mock_inport = MagicMock()
        mock_open_input.return_value = mock_inport
        
        received_triggers = []
        received_ccs = []

        async def mock_trigger_cb(payload):
            received_triggers.append(payload)
            
        async def mock_cc_cb(control, value):
            received_ccs.append((control, value))

        handler = MIDIHandler(trigger_callback=mock_trigger_cb, cc_callback=mock_cc_cb)
        loop = asyncio.get_running_loop()
        handler.start(loop)

        # Simulate MIDI messages
        msg_note = mido.Message('note_on', note=60, velocity=100)
        msg_cc = mido.Message('control_change', control=1, value=64)

        handler._handle_note_on(msg_note.note, msg_note.velocity)
        handler._handle_cc(msg_cc.control, msg_cc.value)

        # Give the event loop a moment to process the threadsafe calls
        await asyncio.sleep(0.1)

        handler.stop()

        self.assertEqual(len(received_triggers), 1)
        self.assertEqual(received_triggers[0]["rule_id"], "midi-note-60")
        self.assertEqual(received_triggers[0]["payload"]["velocity"], 100)
        
        self.assertEqual(len(received_ccs), 1)
        self.assertEqual(received_ccs[0], (1, 64))

if __name__ == '__main__':
    unittest.main()
