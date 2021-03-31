import argparse
import crcmod
from intelhex import IntelHex16bit #Load intelHex


def auto_int(x): # For Hex format reading
    return int(x, 0)

def init_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="""Calculate CRC for dsPIC33EP. ClassB library compatible. CRCMOD: (0x18005, rev=False, initCrc=0xFFFF, xorOut=0x0000).
        """,
        epilog=""" Example: mchpcrccalc.exe input.hex output.hex 0x0 0xADE8 0x2AFFA
        """
    )

    parser.add_argument('infile', metavar='[INPUT.HEX]', type=argparse.FileType('r', encoding='ASCII'))
    
    parser.add_argument('outfile', metavar='[OUTPUT.HEX]', type=argparse.FileType('w', encoding='ASCII'))
    
    parser.add_argument('start', metavar='[START_ADRESS]', type=auto_int,
                    help='CRC will be calculated from this address. (dsPIC program counter address)')
    
    parser.add_argument('length', metavar='[LENGTH]', type=auto_int,
                    help='The length address of the tested flash memory in program counter units.')

    parser.add_argument('crcaddress', metavar='[CRC_STORE_ADDRESS]', type=auto_int,
                    help='CRC will be calculated from this address.')

    parser.add_argument("--verbose", help="increase output verbosity", action="store_true")
    parser.add_argument("-v", "--version", action="version",
                    version = f"{parser.prog} version 1.0.0")    
    return parser


def ExtractHexData(baseAddr, length, intelHex):
    """Rearrange memory map from intelHex to byte array: [Upper,Higher,Lower,Upper,Higher,Lower] This format can be used then for CRC calculation

    Args:
        baseAddr (int): Starting address to extract from hex file (dsPIC program counter address)
        length   (int): The length address of the tested flash memory in program counter units
        intelHex (IntelHex16bit): Extracted data from hex by the IntelHex module.
    Returns:
        bytearray: extraced byte array data, prepared for CRC calculation
    """    
    assert (baseAddr % 2) == 0,"Base address must be even. See dsPIC architecture program counter. See dsPIC architecture and classB lib CRC documentation."
    assert (length % 2) == 0,"Length must be specified as program counter's length. So must be multiple of 2. See dsPIC architecture and classB lib CRC documentation."
    assert (baseAddr + length <= intelHex.maxaddr()), "Address overflow. Check baseAddr, length and loaded hex file max address"
    
    byteLength = length + length//2 #Convert dsPIC program counts to byte count (24bit)
    crcInput = bytearray(byteLength) 
    byteAddr = 0;

    for addr in range(length): # Convert data according to the ClassB CRC implementation

        #check upper or higher,lower address [Upper,Higher,Lower => program word of dsPIC]
        if (addr % 2) == 0: #even means Higher and lower
            intelHex.padding = 0xFFFF;        #padding for Higher 
            crcInput[byteAddr+1] = (intelHex[baseAddr + addr] >> 8 )& 0xFF;    #Get Higher
            intelHex.padding = 0xFF;        #padding for Lower 
            crcInput[byteAddr+2] = intelHex[baseAddr + addr] & 0xFF; #Get Lower

            #print("Addr:", hex(baseAddr+addr), "Higher:", crcInput[byteAddr+1], "Lower:", crcInput[byteAddr+2])

        else: # odd addres mean Upper byte
            crcInput[byteAddr] = intelHex[baseAddr + addr]; 
            #print("Addr:", hex(baseAddr+addr), "Upper:", crcInput[byteAddr])
            byteAddr = byteAddr+3 #increase byteAddress as this was the 
    
    return crcInput  



def main() -> None:
    parser = init_argparse()
    args = parser.parse_args()

    if args.verbose:
        print("verbosity turned on")
        print("Input: " + args.infile.name)
        print("Output: " + args.outfile.name)
        print("Start address: " + hex(args.start))
        print("Length: " + hex(args.length))
        print("Length bytes:", args.length + args.length//2)
        print("CRC Store address: " + hex(args.crcaddress))

    assert (args.start % 2) == 0,"[START_ADDRESS] must be even. This paramter is according to dsPIC architecture program counter. See dsPIC architecture and classB lib CRC documentation."
    assert (args.length % 2) == 0,"[LENGTH] must be specified as program counter's length. So must be multiple of 2. See dsPIC architecture and classB lib CRC documentation."
    assert (args.crcaddress % 2) == 0,"[CRC_STORE_ADDRESS] must be even. This paramter is according to dsPIC architecture program counter.. So must be multiple of 2. See dsPIC architecture and classB lib CRC documentation."

    ih = IntelHex16bit(args.infile) #Open file
    ih.padding = 0xFF #change default padding
    if args.verbose:
        print("Max address in the", args.infile.name, "file:" , hex(ih.maxaddr())) 
    assert (args.start + args.length <= ih.maxaddr()), "Address overflow. Check [START_ADDRESS], [LENGTH] and loaded hex file max address"


    #Read hex and rearrange data to array
    crcInput = ExtractHexData(args.start,args.length,ih)

    #create crc calculator function
    crc16_func = crcmod.mkCrcFun(0x18005, rev=False, initCrc=0xFFFF, xorOut=0x0000)

    #calculate the crc
    crcResult = crc16_func(crcInput)
    if args.verbose:
        print("CRC Result:", hex(crcResult))
    
    #Store the CRC to the selected address
    assert (crcResult <= 0xFFFFF), "Data must fit in 24bit"

    ih[args.crcaddress] = crcResult & 0xFFFF; #load higher and lower byte
    ih[args.crcaddress+1] = (crcResult >> 16) & 0xFF; # load upper byte

    if args.verbose:
        print("Edited address:", hex(args.crcaddress));
        print("Higher and lower byte new data: ", hex(ih[args.crcaddress]));
        print("Upper byte new data: ", hex(ih[args.crcaddress+1]));

    #write out the edited file
    ih.write_hex_file(args.outfile,write_start_addr=False);

if __name__ == "__main__":
    main()