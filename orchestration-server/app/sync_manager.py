import time

class PTPSyncManager:
    """
    Simulates a Precision Time Protocol (PTP) Clock abstraction.
    In a real system, this would interact with the kernel's hardware clock (PTP hardware).
    For our stub, if acts as a time provider that models network latency and jitter
    to calculate true drift against a master clock.
    """
    def __init__(self, master_offset_ms: float = 0.0, jitter_ms: float = 0.5):
        self.master_offset_ms = master_offset_ms
        self.jitter_ms = jitter_ms
        self.is_synced = False
        
    def sync_with_master(self, rtt_ms: float, master_time_diff_ms: float):
        """
        Simulate PTP offset calculation given a network RTT and a master difference.
        Real PTP uses multiple Sync, Follow_Up, Delay_Req, and Delay_Resp messages.
        """
        # PTP offset = (T2 - T1 + T3 - T4) / 2
        # Here we just apply a basic adjustment based on the diff and half the recorded RTT
        self.master_offset_ms = master_time_diff_ms - (rtt_ms / 2.0)
        self.is_synced = True

    def get_time_ms(self) -> int:
        """
        Returns the current timestamp adjusted by the PTP offset.
        Simulates some small read jitter.
        """
        import random
        jitter = random.uniform(-self.jitter_ms, self.jitter_ms)
        real_time_ms = (time.time() * 1000.0) + self.master_offset_ms + jitter
        return int(real_time_ms)
