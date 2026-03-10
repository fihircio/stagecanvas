import asyncio
import cv2
import httpx
import time
from ultralytics import YOLO
import argparse

class InteractionEngine:
    def __init__(self, base_url: str, rule_id: str, camera_id: int = 0):
        self.base_url = base_url.rstrip("/")
        self.rule_id = rule_id
        self.camera_id = camera_id
        self.model = YOLO("yolov8n-pose.pt")  # Load pose model
        self._client = httpx.AsyncClient(timeout=5.0)
        self._stop_event = asyncio.Event()

    async def run(self):
        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            print(f"[interaction-engine] Error: Could not open camera {self.camera_id}")
            return

        print(f"[interaction-engine] Starting YOLO pose tracking for rule {self.rule_id}...")
        
        while not self._stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                break

            # Run YOLO inference
            results = self.model(frame, verbose=False)
            
            # Simple logic: if a person is detected, fire a trigger
            person_detected = False
            for result in results:
                if len(result.boxes) > 0:
                    person_detected = True
                    break

            if person_detected:
                await self.fire_trigger({"detected": True, "timestamp": time.time()})
                # Prevent flooding triggers
                await asyncio.sleep(1.0) 

            # Display for debugging (optional, would be disabled in production)
            # cv2.imshow("StageCanvas Interaction", result.plot())
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
            
            await asyncio.sleep(0.1)

        cap.release()
        cv2.destroyAllWindows()

    async def fire_trigger(self, payload: dict):
        endpoint = f"{self.base_url}/api/v1/triggers/fire"
        try:
            resp = await self._client.post(endpoint, json={
                "rule_id": self.rule_id,
                "payload": payload
            })
            if resp.status_code == 200:
                print(f"[interaction-engine] Fired trigger: {self.rule_id}")
            else:
                print(f"[interaction-engine] Failed to fire trigger: {resp.text}")
        except Exception as e:
            print(f"[interaction-engine] Error sending trigger: {e}")

    async def close(self):
        self._stop_event.set()
        await self._client.aclose()

async def main():
    parser = argparse.ArgumentParser(description="StageCanvas Interaction Engine")
    parser.add_argument("--base-url", default="http://localhost:8010")
    parser.add_argument("--rule-id", default="person-entry")
    parser.add_argument("--camera-id", type=int, default=0)
    args = parser.parse_args()

    engine = InteractionEngine(base_url=args.base_url, rule_id=args.rule_id, camera_id=args.camera_id)
    try:
        await engine.run()
    finally:
        await engine.close()

if __name__ == "__main__":
    asyncio.run(main())
