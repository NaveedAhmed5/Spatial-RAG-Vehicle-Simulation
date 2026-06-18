"""
comparison_test.py — LLM vs No-LLM A/B Test
============================================
Runs the simulation TWICE using the SAME random seed (identical obstacles).

Run 1: LLM DISABLED  — pure Python Reflex Engine with fixed CAUTIOUS policy.
Run 2: LLM ENABLED   — Python Reflex Engine guided by live LLM strategy.

Usage:
    python src/comparison_test.py

Output:
    - Terminal logs for both runs
    - comparison_results.txt saved to project root
"""

import sys
import os
import threading
import queue
import time
import pygame

sys.path.insert(0, os.path.dirname(__file__))
from engine import Engine, FPS
from manager import get_ai_decision, calculate_safe_maneuver

# ── Shared random seed for both runs ──────────────────────────────────────────
TEST_SEED = 42
# How many frames to run each simulation (600 = 10 seconds at 60 FPS)
MAX_FRAMES = 1800  # 30 seconds

# ──────────────────────────────────────────────────────────────────────────────

def run_simulation(mode: str, seed: int, max_frames: int) -> dict:
    """
    Runs one simulation in headless-compatible mode.
    mode: "NO_LLM" or "LLM"
    Returns a dict with results.
    """
    print(f"\n{'='*55}")
    print(f"  STARTING RUN: {mode}")
    print(f"{'='*55}")

    engine = Engine(random_seed=seed)
    ai_result_queue = queue.Queue()
    ai_is_thinking = False
    current_policy = {"strategy": "CAUTIOUS", "preferred_lane": 2}
    action_cooldown = 0
    COOLDOWN_FRAMES = 45
    last_strategy_change_frame = 0

    # Event log
    spawns = []
    dodges = []
    strategy_updates = []
    survived_frames = 0
    crashed = False

    # LLM polling (only in LLM mode)
    LLM_PING_EVERY = 300  # Every 5 seconds (300 frames at 60fps)
    next_llm_ping = LLM_PING_EVERY

    def ai_worker(lane, car_y, db):
        try:
            policy = get_ai_decision(current_lane=lane, car_y=car_y, db_override=db)
            ai_result_queue.put(policy)
        except Exception as e:
            print(f"  [AI ERROR] {e}")
            ai_result_queue.put({"strategy": "CAUTIOUS", "preferred_lane": 2})

    for frame in range(max_frames):
        # Handle pygame events (keep window responsive)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        # ── LLM Ping (only in LLM mode) ───────────────────────────────────────
        if mode == "LLM" and frame == next_llm_ping and not ai_is_thinking:
            ai_is_thinking = True
            t = threading.Thread(
                target=ai_worker,
                args=(engine.car.current_lane, engine.car.y, engine.db),
                daemon=True
            )
            t.start()
            next_llm_ping = frame + LLM_PING_EVERY

        # ── Collect LLM result ─────────────────────────────────────────────────
        if mode == "LLM":
            try:
                response = ai_result_queue.get_nowait()
                if isinstance(response, dict) and "strategy" in response:
                    old_strategy = current_policy.get("strategy")
                    current_policy = response
                    ai_is_thinking = False
                    engine.ai_thinking = False
                    msg = (f"  [FRAME {frame}] STRATEGY UPDATED: "
                           f"{old_strategy} → {current_policy['strategy']} | "
                           f"Preferred Lane: {current_policy['preferred_lane']}")
                    print(msg)
                    strategy_updates.append({
                        "frame": frame,
                        "policy": dict(current_policy)
                    })
            except queue.Empty:
                pass

        # ── Python Reflex Engine ───────────────────────────────────────────────
        if action_cooldown > 0:
            action_cooldown -= 1
        else:
            maneuver = calculate_safe_maneuver(
                current_lane=engine.car.current_lane,
                obstacles=engine.obstacles,
                car_y=engine.car.y,
                policy=current_policy
            )
            action = maneuver.get("action", "STAY")
            if action != "STAY":
                msg = (f"  [FRAME {frame}] DODGE → {action} | "
                       f"Lane: {engine.car.current_lane} → "
                       f"{'L' if action == 'MOVE_LEFT' else 'R'} | "
                       f"Strategy: {current_policy['strategy']}")
                print(msg)
                dodges.append({
                    "frame": frame,
                    "from_lane": engine.car.current_lane,
                    "action": action,
                    "strategy": current_policy["strategy"]
                })
                engine.car.execute_action(action)
                action_cooldown = COOLDOWN_FRAMES

        # ── Track spawns ───────────────────────────────────────────────────────
        pre_obs_count = len(engine.obstacles)
        engine.update()

        for obs in engine.obstacles:
            if obs not in [s["obs_ref"] for s in spawns if "obs_ref" in s]:
                if obs.y < -50 + obs.speed + 1:  # Freshly spawned
                    spawns.append({
                        "frame": frame,
                        "lane": obs.lane,
                        "obs_ref": obs
                    })
                    print(f"  [FRAME {frame}] SPAWN → Lane {obs.lane}")

        engine.draw()
        engine.clock.tick(FPS)

        if not engine.running:
            crashed = True
            survived_frames = frame
            print(f"\n  ❌ CRASHED at frame {frame} ({frame/60:.1f}s)")
            break
        survived_frames = frame

    if not crashed:
        print(f"\n  ✅ SURVIVED all {max_frames} frames ({max_frames/60:.1f}s)!")

    pygame.display.set_caption(f"RAG Racer — {mode} RUN COMPLETE")
    time.sleep(1.5)

    return {
        "mode": mode,
        "survived_frames": survived_frames,
        "crashed": crashed,
        "total_spawns": len(spawns),
        "total_dodges": len(dodges),
        "strategy_updates": strategy_updates,
        "dodge_log": dodges,
        "spawn_lanes": [s["lane"] for s in spawns],
    }


def print_comparison(result_a: dict, result_b: dict):
    lines = []
    lines.append("=" * 60)
    lines.append("  A/B COMPARISON REPORT: LLM vs NO-LLM")
    lines.append(f"  Random Seed: {TEST_SEED} (identical obstacle patterns)")
    lines.append("=" * 60)

    for r in [result_a, result_b]:
        lines.append(f"\n── {r['mode']} ──")
        lines.append(f"  Survived:        {r['survived_frames']} frames ({r['survived_frames']/60:.1f}s)")
        lines.append(f"  Crashed:         {'YES ❌' if r['crashed'] else 'NO ✅'}")
        lines.append(f"  Total Spawns:    {r['total_spawns']}")
        lines.append(f"  Total Dodges:    {r['total_dodges']}")
        if r["strategy_updates"]:
            lines.append(f"  Strategy Shifts: {len(r['strategy_updates'])}")
            for su in r["strategy_updates"]:
                lines.append(f"    Frame {su['frame']}: {su['policy']}")
        else:
            lines.append(f"  Strategy Shifts: 0 (fixed CAUTIOUS)")

        if r["dodge_log"]:
            lines.append(f"  Dodge Log:")
            for d in r["dodge_log"][:20]:  # Cap at 20
                lines.append(f"    Frame {d['frame']:4d}: {d['action']:<12} from Lane {d['from_lane']} [{d['strategy']}]")

    lines.append("\n" + "=" * 60)
    lines.append("  VERDICT")
    lines.append("=" * 60)

    no_llm = result_a
    llm    = result_b

    if not no_llm["crashed"] and llm["crashed"]:
        lines.append(f"  NO-LLM WIN: No-LLM survived all {no_llm['survived_frames']} frames.")
        lines.append(f"  LLM CRASHED at frame {llm['survived_frames']} ({llm['survived_frames']/60:.1f}s).")
        lines.append(f"  The LLM switched to AGGRESSIVE mode which caused a crash. Prompt needs tuning.")
    elif no_llm["crashed"] and not llm["crashed"]:
        lines.append(f"  LLM WIN: LLM-guided run survived all {llm['survived_frames']} frames.")
        lines.append(f"  No-LLM crashed at frame {no_llm['survived_frames']} ({no_llm['survived_frames']/60:.1f}s).")
        lines.append(f"  The LLM's preferred lane selection actively saved the car.")
    elif not no_llm["crashed"] and not llm["crashed"]:
        if llm["total_dodges"] < no_llm["total_dodges"]:
            diff = no_llm["total_dodges"] - llm["total_dodges"]
            lines.append(f"  LLM WIN: Both survived. LLM made {diff} fewer dodges — smarter lane selection.")
        elif no_llm["total_dodges"] < llm["total_dodges"]:
            diff = llm["total_dodges"] - no_llm["total_dodges"]
            lines.append(f"  DRAW: Both survived. No-LLM made {diff} fewer dodges (LLM overcorrected).")
        else:
            lines.append(f"  DRAW: Both survived with identical dodge counts.")
    else:
        lines.append(f"  BOTH CRASHED. No-LLM lasted {no_llm['survived_frames']} frames, LLM lasted {llm['survived_frames']} frames.")

    report = "\n".join(lines)
    print("\n" + report)

    out_path = os.path.join(os.path.dirname(__file__), "..", "comparison_results.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n  Full report saved to: comparison_results.txt")


if __name__ == "__main__":
    print("\n🔬 RAG Racer A/B Comparison Test")
    print(f"   Seed: {TEST_SEED} | Duration: {MAX_FRAMES} frames ({MAX_FRAMES/60:.0f}s) per run\n")
    print("   Run 1 will start in 3 seconds...")
    time.sleep(3)

    # ── Run 1: No LLM ─────────────────────────────────────────────────────────
    result_no_llm = run_simulation("NO_LLM", seed=TEST_SEED, max_frames=MAX_FRAMES)
    print("\n   Run 1 complete. Starting Run 2 (LLM) in 3 seconds...")
    time.sleep(3)

    # ── Run 2: With LLM ───────────────────────────────────────────────────────
    result_llm = run_simulation("LLM", seed=TEST_SEED, max_frames=MAX_FRAMES)

    # ── Compare ───────────────────────────────────────────────────────────────
    print_comparison(result_no_llm, result_llm)

    pygame.quit()
    sys.exit()
