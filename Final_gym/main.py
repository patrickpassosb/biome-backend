from scripts.realtime_match import run_live_match

def main():
    print("\n=== AI GYM TRAINER ===\n")
    print("Select Exercise:")
    print("1. Push-up")
    print("2. Squat")
    print("3. Deadlift")
    print("4. Plank")
    print("5. Lunge")
    print("6. Pull-up\n")

    choice = input("Enter number: ")

    exercise_map = {
        "1": ("refs/ref_pushup.npy", "pushup"),
        "2": ("refs/ref_squat.npy", "squat"),
        "3": ("refs/ref_deadlift.npy", "deadlift"),
        "4": ("refs/ref_plank.npy", "plank"),
        "5": ("refs/ref_lunge.npy", "lunge"),
        "6": ("refs/ref_pullup.npy", "pullup"),
    }

    if choice not in exercise_map:
        print("Invalid choice!")
        return

    ref_path, name = exercise_map[choice]
    print(f"\nLoading reference → {ref_path}")
    print(f"Starting {name} trainer... (press Q to exit)\n")

    run_live_match(ref_path, name)

if __name__ == "__main__":
    main()
