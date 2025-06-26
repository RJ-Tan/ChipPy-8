import numpy as np
import pygame 
import random
import time
from time import perf_counter

START_ADDRESS = 0x200
START_ADDRESS_FONTS = 0x50

class Chip8Display(pygame.Surface):
    def __init__(self):
        super().__init__((64, 32))
        self.fill((0,0,0))
        self.displayArray = np.zeros((32, 64), dtype='uint8')
        
    def clear(self):
        self.fill((0,0,0))

    def getPixelArray(self):
        return pygame.PixelArray(self)

class Chip8Keypad:
    CHAR_TR = { '1':0x1, '2':0x2, '3':0x3, '4':0xC,
                'q':0x4, 'w':0x5, 'e':0x6, 'r':0xD,
                'a':0x7, 's':0x8, 'd':0x9, 'f':0xE,
                'z':0xA, 'x':0x0, 'c':0xB, 'v':0xF}
    def __init__(self):
        self.keydownBools = np.zeros((16,), dtype='bool')
        self.numKeypresses = 0
        self.currentKeypress = None

    def registerKeydown(self, c:str):
        if c in self.CHAR_TR:
            self.keydownBools[self.CHAR_TR[c]] = True

    def registerKeyup(self, c:str):
        if c in self.CHAR_TR:
            self.keydownBools[self.CHAR_TR[c]] = False
            self.currentKeypress = self.CHAR_TR[c]

class Chip8Timer:
    def __init__(self):
        self.delay = 0
        self.sound = 0
    
    def decrement(self):
        self.delay -= 1 if self.delay > 0 else 0
        self.sound -= 1 if self.sound > 0 else 0

class Chip8:
    def __init__(self, inspeed, display:Chip8Display, keypad:Chip8Keypad, timer:Chip8Timer):
        self.registers = np.zeros((16,), dtype='uint8')
        self.memory = np.empty((4096,), dtype='uint8')
        self.indexRegister = np.zeros((1,), dtype='uint16' )
        self.pc = np.array([START_ADDRESS], dtype='uint16')
        self.pcStack = np.zeros((16,), dtype='uint16')
        self.stackPointer = np.zeros((1,), dtype='uint8')
        self.display = display
        self.keypad = keypad
        self.timer = timer
        self.timing = 1 / inspeed # min time between instructions, measured in seconds
        self.prevCycle = perf_counter()
        self.awaitingKeyInput = False

    def loadROM(self, filename:str):
        """Load a ROM file into memory"""
        with open(filename, 'rb') as f:
            data = f.read()
            for i in range(len(data)):
                self.memory[START_ADDRESS + i] = data[i]

    def loadFonts(self, fontData:np.ndarray):
        start = 0x50 #the starting address for fonts in memory
        self.memory[start:start+ fontData.shape[0] * fontData.shape[1]] = fontData.flatten()

    def fetchCurrentInstruction(self):
        # Fetch the instruction at memory location pointed to by the PC and increment the PC by 2
        opcode = np.uint16(self.memory[self.pc[0]]) << 8 | np.uint16(self.memory[self.pc[0] + 1])
        self.pc[0] += 2
        return opcode

    def executeInstruction(self, instruction:np.uint16):

        match instruction & 0xF000:
            case 0x0000:
                if instruction == 0x00E0:
                    # 00E0 instruction: Clear display
                    self.display.clear()
                    print("Clear display")
                elif instruction == 0x00EE:
                    # 00EE instruction: Return from subroutine
                    self.pc[0] = self.pcStack[self.stackPointer[0] - 1]
                    self.stackPointer[0] -= 1
                else:
                    # 0nnn instruction: Jump to a machine code routine at nnn
                    # Was only used in the original CHIP-8 on old computers, so no need to implement
                    pass

            case 0x1000:
                # 1nnn instruction: Jump to address nnn
                addr = instruction & 0x0FFF
                self.pc[0] = addr 

            case 0x2000:
                # 2nnn instruction: Call subroutine at nnn
                addr = instruction & 0x0FFF
                self.stackPointer[0] += 1
                self.pcStack[self.stackPointer[0] - 1] = self.pc[0]
                self.pc[0] = addr

            case 0x3000:
                # 3xnn instruction: Increment pc by 2 if the contents of register x equals nn
                x = (instruction & 0x0F00) >> 8
                nn = instruction & 0x00FF
                if self.registers[x] == nn:
                    self.pc[0] += 2

            case 0x4000:
                # 4xnn instruction: Increment pc by 2 if the contents of register x does not equal nn
                x = (instruction & 0x0F00) >> 8
                nn = instruction & 0x00FF
                if self.registers[x] != nn:
                    self.pc[0] += 2

            case 0x5000:
                # 5xy0 instruction: Increment pc by 2 if the contents of registers x and y are equal
                x = (instruction & 0x0F00) >> 8
                y = (instruction & 0x00F0) >> 4
                if self.registers[x] == self.registers[y]:
                    self.pc[0] += 2

            case 0x6000:
                # 6xnn instruction: Puts NN into register X 
                x = (instruction & 0x0F00) >> 8
                nn = instruction & 0x00FF
                self.registers[x] = np.uint8(nn)

            case 0x7000:
                # 7xnn instruction: Adds nn to register x
                x = (instruction & 0x0F00) >> 8
                nn = instruction & 0x00FF
                self.registers[x] = np.uint8((self.registers[x] + nn)%256) # Performs '% 256' to ensure the sum fits into 8bits

            case 0x8000:
                x = (instruction & 0x0F00) >> 8
                y = (instruction & 0x00F0) >> 4
                match instruction & 0x000F:
                    case 0x0:
                        # 8xy0 instruction: Sets register x to the content of register y
                        self.registers[x] = self.registers[y]
                    case 0x1:
                        # 8xy1 instruction: Sets register x to the bitwise OR on the contents of registers x and y
                        self.registers[x] = self.registers[x] | self.registers[y]
                    case 0x2:
                        # 8xy2 instruction: Perform bitwise AND on the contents of registers x and y, then store in register x 
                        self.registers[x] = self.registers[x] & self.registers[y]
                    case 0x3:
                        # 8xy3 instruction: Perform bitwise XOR on the contents of registers x and y, then store in register x
                        self.registers[x] = self.registers[x] ^ self.registers[y]
                    case 0x4:
                        # 8xy4 instruction: Adds the contents of register y to register x, sets  VF to 1 if there is a carry, 0 otherwise
                        sumxy = np.uint16(self.registers[x]) + self.registers[y]
                        self.registers[x] = np.uint8(sumxy & 0x00FF)
                        if sumxy > 255:
                            self.registers[0xF] = 1
                        else:
                            self.registers[0xF] = 0
                    case 0x5:
                        # 8xy5 instruction
                        cmpx, cmpy = int(self.registers[x]), int(self.registers[y])
                        diffxy = self.registers[x] - self.registers[y]
                        self.registers[x] = diffxy
                        if cmpx < cmpy:
                            self.registers[0xF] = 0
                        else:
                            self.registers[0xF] = 1
                    case 0x6:
                        # 8xy6 instruction: Store lsb of x in register F, then shift register x right by 1
                        lsb = self.registers[x] & 1
                        self.registers[x] = np.uint8(self.registers[x] >> 1) 
                        self.registers[0xF] = lsb
                    case 0x7:
                        # 8xy7 instruction: Register x = Register y - Register x
                        cmpx, cmpy = int(self.registers[x]), int(self.registers[y])
                        self.registers[x] = self.registers[y] - self.registers[x]
                        if cmpy < cmpx:
                            self.registers[0xF] = 0
                        else:
                            self.registers[0xF] = 1
                    case 0xE:
                        # 8xyE instruction: store msb of x in register F, then shift register x left by 1
                        msb = self.registers[x] & 128 #1000 0000
                        self.registers[x] = np.uint8(self.registers[x] << 1)
                        self.registers[0xF] = msb >> 7
                        
            case 0x9000:
                # 9xy0 instruction: Increments pc by 2 if the contents of registers x and y are not equal
                x = (instruction & 0x0F00) >> 8
                y = (instruction & 0x00F0) >> 4
                if self.registers[x] != self.registers[y]:
                    self.pc[0] += 2

            case 0xA000:
                # Annn instruction: Sets the index register to the memory address nnn
                nnn = instruction & 0x0FFF
                self.indexRegister[0] = np.uint16(nnn)

            case 0xB000:
                # Bnnn instruction: Jumps to address nnn plus register 0
                nnn = instruction & 0x0FFF
                self.pc = np.uint16(nnn) + self.registers[0]

            case 0xC000:
                # Cxnn instruction
                x = (instruction & 0x0F00) >> 8
                nn = instruction & 0x00FF
                self.registers[x] = np.uint8(random.randint(0,255)) & np.uint8(nn) 

            case 0xD000:
                # Dxyn instruction: Display n byte sprite from memory pointed to by the index register at coordinates (Vx, Vy) on the display 
                # VF is set to 1 if any pixels are flipped from set to unset (1 to 0) and 0 otherwise
                x = (instruction & 0x0F00) >> 8
                y = (instruction & 0x00F0) >> 4
                n = instruction & 0x000F
                vxCoord = self.registers[x] % 64
                vyCoord = self.registers[y] % 32

                ON_BIT = self.display.map_rgb((255, 255, 255))
                OFF_BIT = self.display.map_rgb((0, 0, 0)) 

                pixelArray = self.display.getPixelArray()
                self.display.lock()
                self.registers[0xF] = 0
                for i in range(n):
                    spriteByte = np.unpackbits(self.memory[self.indexRegister[0] + i])
                  
                    for j in range(8):
                        spriteBit = spriteByte[j]
                        if spriteBit == 0:
                            continue

                        if pixelArray[int((vxCoord + j) % 64), int((vyCoord + i) % 32)] == ON_BIT:
                            self.registers[0xF] = 1
                            pixelArray[int((vxCoord + j) % 64), int((vyCoord + i) % 32) ] = OFF_BIT
                        else:
                            newx, newy = (vxCoord + j) % 64, (vyCoord + i) % 32
                            
                            pixelArray[int(newx), int(newy)] = ON_BIT
                self.display.unlock()    
            
            case 0xE000:
                x = (instruction & 0x0F00) >> 8
                
                match instruction & 0x00FF:
                    case 0x009E:
                        # Ex9E instruction
                        if self.keypad.keydownBools[self.registers[x]] == True:
                            self.pc[0] += 2 
                    case 0x00A1:
                        # ExA1 instruction
                        if self.keypad.keydownBools[self.registers[x]] == False:
                            self.pc[0] += 2 

            case 0xF000:
                x = (instruction & 0x0F00) >> 8

                match instruction & 0x00FF:
                    case 0x07:
                        #Fx07 instruction: Sets register x to the value of dt
                        self.registers[x] = self.timer.delay
                    case 0x0A:
                        #Fx0A instruction: halt execution cycle until keypress
                        if self.awaitingKeyInput == False:
                            self.awaitingKeyInput = True
                            self.keypad.currentKeypress = None
                        
                        if self.awaitingKeyInput == True and self.keypad.currentKeypress == None:
                            self.pc[0] -= 2
                        elif self.awaitingKeyInput == True and self.keypad.currentKeypress != None:
                            self.awaitingKeyInput = False
                            self.registers[x] = np.uint8(self.keypad.currentKeypress)
                    case 0x15:
                        #Fx15 instruction: Set delay timer to value of register x
                        self.timer.delay = int(self.registers[x])
                    case 0x18:
                        #Fx18 instruction: Set sound timer to value of register x
                        self.timer.sound = int(self.registers[x])
                    case 0x1E:
                        #Fx1E instruction: Adds register X to I
                        self.indexRegister[0] += np.uint16(self.registers[x])
                    case 0x29:
                        #Fx29 instruction: Sets index register to location of sprite for character in register x
                        self.indexRegister[0] = START_ADDRESS_FONTS + np.uint16(self.registers[x]) * 5
                    case 0x33:
                        # Fx33 instruction
                        self.memory[self.indexRegister[0]] = self.registers[x] // 100
                        self.memory[self.indexRegister[0] + 1] = (self.registers[x] // 10) % 10
                        self.memory[self.indexRegister[0] + 2] = self.registers[x] % 10
                    case 0x55:
                        # Fx55 instruction
                        for i in range(self.indexRegister[0], np.uint16(self.indexRegister[0] + x + 1)):
                            self.memory[i] = self.registers[i - self.indexRegister[0]]
                    case 0x65:
                        # Fx65 instruction
                        for i in range(self.indexRegister[0], np.uint16(self.indexRegister[0] + x + 1)):
                            self.registers[i - self.indexRegister[0]] = self.memory[i]

            case _:
                print("Unknown instruction:", hex(instruction))

