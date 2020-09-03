import unittest
import midi
import time
import os

try:
    import midi.sequencer as sequencer
except (ImportError, AttributeError):
    sequencer = None


def get_sequencer_type():
    return sequencer.Sequencer.SEQUENCER_TYPE if hasattr(sequencer, "Sequencer") else None


class TestMIDI(unittest.TestCase):
    def test_varlen(self):
        maxval = 0x0FFFFFFF
        for inval in range(0, maxval, maxval // 1000):
            datum = midi.write_varlen(inval)
            outval = midi.read_varlen(iter(datum))
            self.assertEqual(inval, outval, f"0x{inval:x} -> {datum} -> {outval:x}")

    def test_mary(self):
        test_midi = midi.Pattern(tracks=[
            midi.Track(events=[
                midi.events.TimeSignatureEvent(tick=0, data=[4, 2, 24, 8]),
                midi.events.KeySignatureEvent(tick=0, data=[0, 0]),
                midi.events.EndOfTrackEvent(tick=1, data=[])
            ]),
            midi.Track(events=[
                midi.events.ControlChangeEvent(tick=0, channel=0, data=[91, 58]),
                midi.events.ControlChangeEvent(tick=0, channel=0, data=[32, 0]),
                midi.events.ProgramChangeEvent(tick=0, channel=0, data=[24]),
                midi.events.NoteOnEvent(tick=0, channel=0, data=[64, 72]),
                midi.events.NoteOnEvent(tick=0, channel=0, data=[55, 70]),
                midi.events.NoteOnEvent(tick=231, channel=0, data=[64, 0]),
                midi.events.NoteOnEvent(tick=0, channel=0, data=[52, 0]),
                midi.events.EndOfTrackEvent(tick=1, data=[])
            ])
        ])

        midi.write_midifile("mary.mid", test_midi)
        pattern1 = midi.read_midifile("mary.mid")

        midi.write_midifile("mary.mid", pattern1)
        pattern2 = midi.read_midifile("mary.mid")

        self.assertEqual(len(pattern1), len(pattern2))

        for track_idx in range(len(pattern1)):
            self.assertEqual(len(pattern1[track_idx]), len(pattern2[track_idx]))

            for event_idx in range(len(pattern1[track_idx])):
                event1 = pattern1[track_idx][event_idx]
                event2 = pattern2[track_idx][event_idx]
                self.assertEqual(event1.tick, event2.tick)
                self.assertEqual(event1.data, event2.data)

    def test_slicing_containers(self):
        pattern = midi.Pattern()
        pattern.extend([midi.Track()] * 5)
        result1 = pattern[1]
        result2 = pattern[1:5]
        result3 = pattern[::2]

        track = midi.Track()
        track.extend([midi.Event()] * 5)
        result1 = track[1]
        result2 = track[1:5]
        result3 = track[::2]


class TestSequencerALSA(unittest.TestCase):
    TEMPO = 120
    RESOLUTION = 1000

    def get_loop_client_port(self):
        hw = sequencer.SequencerHardware()
        ports = {port.name: port for port in hw}
        loop = ports.get("Midi Through", None)
        assert loop != None, "Could not find Midi Through port!"
        loop_port = loop.get_port("Midi Through Port-0")
        return (loop.client, loop_port.port)

    def get_reader_sequencer(self):
        (client, port) = self.get_loop_client_port()
        seq = sequencer.SequencerRead(sequencer_resolution=self.RESOLUTION)
        seq.subscribe_port(client, port)
        return seq

    def get_writer_sequencer(self):
        (client, port) = self.get_loop_client_port()
        seq = sequencer.SequencerWrite(sequencer_resolution=self.RESOLUTION)
        seq.subscribe_port(client, port)
        return seq

    @unittest.skipIf(get_sequencer_type() != "alsa", "ALSA Sequencer not found, skipping test")
    @unittest.skipIf(not os.access("/dev/snd/seq", os.R_OK | os.W_OK), "/dev/snd/seq is not available, skipping test")
    def test_loopback_sequencer(self):
        rseq = self.get_reader_sequencer()
        wseq = self.get_writer_sequencer()
        start_time = time.time()
        delay = 0.6
        rseq.start_sequencer()
        wseq.start_sequencer()
        tick = int((self.TEMPO / 60.0) * self.RESOLUTION * delay)
        send_event = midi.NoteOnEvent(tick=tick, velocity=20, pitch=midi.G_3)
        wseq.event_write(send_event, False, False, True)
        recv_event = rseq.event_read()
        while 1:
            now = time.time()
            recv_event = rseq.event_read()
            if recv_event is not None:
                break
            if (now - start_time) > (2 * delay):
                break
            time.sleep(.01)
        delta = now - start_time
        # make sure we received this event at the proper time
        self.assertGreaterEqual(delta, delay)
        # make sure this event is the one we transmitted
        self.assertEqual(send_event.data, recv_event.data)
        self.assertEqual(send_event.__class__, recv_event.__class__)


if __name__ == '__main__':
    unittest.main()
