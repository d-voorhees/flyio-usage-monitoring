"""
Derive CPU_RATE_PER_HOUR and MEMORY_RATE_PER_GB_HOUR from Fly.io's published
per-second pricing.

Fly prices a machine as one bundled number per (CPU tier, RAM size) — e.g.
shared-cpu-1x @ 256MB costs $0.00000075/s. This script takes two or more
(RAM, price-per-second) pairs from the SAME CPU tier off Fly's pricing page
and solves for the implied per-vCPU and per-GB-RAM hourly rates, since:

    price_per_second = cpu_rate_per_second + ram_gb * mem_rate_per_second

Usage:
    python calculate_rates.py 256:0.00000075 512:0.00000123

Each argument is RAM_MB:PRICE_PER_SECOND, copied straight from
https://fly.io/docs/about/pricing/ for a single CPU tier (e.g. shared-cpu-1x).
Provide at least two points from that tier's different RAM sizes. Extra
points beyond two are least-squares fit and checked for consistency.
"""
import sys


def parse_points(args):
    points = []
    for arg in args:
        try:
            ram_str, price_str = arg.split(":")
            ram_gb = float(ram_str) / 1024
            price = float(price_str)
        except ValueError:
            raise SystemExit(
                f"Bad argument {arg!r}. Expected RAM_MB:PRICE_PER_SECOND, "
                "e.g. 256:0.00000075"
            )
        points.append((ram_gb, price))
    return points


def solve_rates(points):
    n = len(points)
    if n < 2:
        raise SystemExit(
            "Need at least two RAM_MB:PRICE_PER_SECOND points from the same "
            "CPU tier."
        )

    sum_x = sum(x for x, _ in points)
    sum_y = sum(y for _, y in points)
    sum_xx = sum(x * x for x, _ in points)
    sum_xy = sum(x * y for x, y in points)

    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        raise SystemExit(
            "All RAM values are identical — can't separate CPU cost from "
            "RAM cost."
        )

    mem_rate_per_second = (n * sum_xy - sum_x * sum_y) / denom
    cpu_rate_per_second = (sum_y - mem_rate_per_second * sum_x) / n

    return cpu_rate_per_second, mem_rate_per_second


def main():
    if len(sys.argv) < 3:
        raise SystemExit(
            "Usage: python calculate_rates.py RAM_MB:PRICE_PER_SECOND "
            "RAM_MB:PRICE_PER_SECOND [...]\n"
            "Example: python calculate_rates.py 256:0.00000075 "
            "512:0.00000123\n"
            "Copy these straight from https://fly.io/docs/about/pricing/ "
            "for a single CPU tier."
        )

    points = parse_points(sys.argv[1:])
    cpu_rate_per_second, mem_rate_per_second = solve_rates(points)

    cpu_rate_per_hour = cpu_rate_per_second * 3600
    mem_rate_per_hour = mem_rate_per_second * 3600

    print("Fit check (predicted vs. given price per second):")
    for ram_gb, price in points:
        predicted = cpu_rate_per_second + ram_gb * mem_rate_per_second
        diff = predicted - price
        off = abs(diff / price) > 0.01 if price else False
        flag = "  <- off by more than 1%, double-check these are the same CPU tier" if off else ""
        print(f"  {ram_gb * 1024:.0f}MB: given ${price:.8f}, predicted ${predicted:.8f}{flag}")

    print()
    print("Set these GitHub secrets:")
    print(f"  CPU_RATE_PER_HOUR = {cpu_rate_per_hour:.6f}")
    print(f"  MEMORY_RATE_PER_GB_HOUR = {mem_rate_per_hour:.6f}")


if __name__ == "__main__":
    main()
