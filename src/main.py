import numpy as np
import pygame
import sys
import threading
from time import perf_counter
from chip8 import Chip8, Chip8Display, Chip8Keypad, Chip8Timer

if len(sys.argv) < 2:
    sys.exit("Usage: py main.py <rom_path> <instruction_speed=700>")
elif len(sys.argv) == 3 and not sys.argv[2].isdecimal():
    sys.exit("Instruction speed must be a number, default value is 700")

romPath = sys.argv[1]
instructionSpeed = int(sys.argv[2]) if len(sys.argv) >= 3 else 700

# Constant
FONT_DATA = np.array([
    [0xF0, 0x90, 0x90, 0x90, 0xF0], # 0
    [0x20, 0x60, 0x20, 0x20, 0x70], # 1
    [0xF0, 0x10, 0xF0, 0x80, 0xF0], # 2
    [0xF0, 0x10, 0xF0, 0x10, 0xF0], # 3
    [0x90, 0x90, 0xF0, 0x10, 0x10], # 4
    [0xF0, 0x80, 0xF0, 0x10, 0xF0], # 5
    [0xF0, 0x80, 0xF0, 0x90, 0xF0], # 6
    [0xF0, 0x10, 0x20, 0x40, 0x40], # 7
    [0xF0, 0x90, 0xF0, 0x90, 0xF0], # 8
    [0xF0, 0x90, 0xF0, 0x10, 0xF0], # 9
    [0xF0, 0x90, 0xF0, 0x90, 0x90], # A
    [0xE0, 0x90, 0xE0, 0x90, 0xE0], # B
    [0xF0, 0x80, 0x80, 0x80, 0xF0], # C
    [0xE0, 0x90, 0x90, 0x90, 0xE0], # D
    [0xF0, 0x80, 0xF0, 0x80, 0xF0], # E
    [0xF0, 0x80, 0xF0, 0x80, 0x80]  # F
], dtype='uint8')

chip8Display = Chip8Display()
chip8Keypad = Chip8Keypad()
chip8Timer = Chip8Timer()
chip8 = Chip8(instructionSpeed, chip8Display, chip8Keypad, chip8Timer)

chip8.loadROM(romPath)
chip8.loadFonts(FONT_DATA)

running = True

def FetchExecuteLoop():
    global running
    while running:
        current = perf_counter()

        if (current - chip8.prevCycle) < chip8.timing:
            continue

        op = chip8.fetchCurrentInstruction()
        chip8.executeInstruction(op)
        chip8.prevCycle = current

def DisplayLoop():
    pygame.init() # Initialize pygame for display
    clock = pygame.time.Clock()
    screen = pygame.display.set_mode((800, 600), pygame.RESIZABLE)
    pygame.display.set_caption("Chip-8 Emulator")

    scaledChip8Display = pygame.Surface((64 * 10, 32 * 10))

    global running
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                chip8Keypad.registerKeydown(event.dict['unicode'])
            elif event.type == pygame.KEYUP:
                chip8Keypad.registerKeyup(event.dict['unicode'])

        pygame.transform.scale(chip8Display, scaledChip8Display.get_size(), scaledChip8Display)
        xMid = (pygame.display.get_surface().get_width() // 2) - scaledChip8Display.get_width() // 2
        yMid = (pygame.display.get_surface().get_height()//2) - scaledChip8Display.get_height()//2
        screen.blit(scaledChip8Display, (xMid,yMid))
        pygame.display.flip()

        chip8Timer.decrement()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    
    t1 = threading.Thread(target=FetchExecuteLoop)
    t2 = threading.Thread(target=DisplayLoop)

    t2.start()
    t1.start()

    t1.join()

    print("Emulator Fin")


# resources:
# http://devernay.free.fr/hacks/chip8/C8TECH10.HTM
# https://en.wikipedia.org/wiki/CHIP-8
# https://tobiasvl.github.io/blog/write-a-chip-8-emulator/