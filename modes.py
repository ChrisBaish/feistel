from iterators import eof_signal_iterator
from galois import GaloisPolynomial as GP

""" Classes implementing modes of encryption:

* We can extend this, currently only ECB, CBC and CTR is supported

"""
class ModeOfOperation():
    def __init__(self, cipher, iv = None, nonce = None):
        self.cipher = cipher
        self.iv = iv
        self.nonce = nonce
        self.block_size = cipher.block_size

    def _xor(self, block1, block2):
        return bytes([a ^ b for a, b in zip(block1, block2)])

class ECB(ModeOfOperation):
    def __init__(self, cipher, padding_scheme):
        super(ECB, self).__init__(cipher)
        self.padding_scheme = padding_scheme

    def encrypt(self, block_iterator):
        # Wrap file / list iterator inside eof_signal_iterator
        eof_iterator = eof_signal_iterator(block_iterator)

        for data, eof in eof_iterator:
            if not eof:
                ciphertext = self.cipher.encrypt_block(data)
            else:
                block = data if not eof else self.padding_scheme.apply(data)
                # Padding should return 1 or 2 blocks
                if len(block) == self.block_size:
                    ciphertext = self.cipher.encrypt_block(block)
                elif len(block) == self.block_size * 2:
                    ciphertext = self.cipher.encrypt_block(block[:self.block_size]) \
                               + self.cipher.encrypt_block(block[self.block_size:])

                else:
                    raise Exception("Padding error: Padding scheme returned data that is not a multiple of the block length")
            yield ciphertext

    def decrypt(self, block_iterator):
        # Wrap file / list iterator inside eof_signal_iterator
        eof_iterator = eof_signal_iterator(block_iterator)

        for data, eof in eof_iterator:
            plaintext = self.cipher.decrypt_block(data)
            block = plaintext if not eof else self.padding_scheme.remove(plaintext)
            yield block

#CBC mode implemented by Lucas V. Araujo <https://github.com/LvMalware/>

#CBC encrypts each block xor'd against the cipher text of the previous block.
#The first block is xor'd against a 0th block, the initialization vector (IV)

class CBC(ModeOfOperation):

    def __init__(self, cipher, iv, padding_scheme):
        super(CBC, self).__init__(cipher=cipher, iv=iv)
        #initialize cipher_block with value None
        self.cipher_block = None
        self.padding_scheme = padding_scheme

    def encrypt(self, block_iterator):
        eof_iterator = eof_signal_iterator(block_iterator)
        for data, eof in eof_iterator:

            if not self.cipher_block:
                #executed only once, on the first iteration
                self.cipher_block = self.iv
                #just return the IV, to be used as the first 64 bytes of the file
                yield self.cipher_block

            if not eof:
                self.cipher_block = self.cipher.encrypt_block(
                    self._xor(data, self.cipher_block)
                )
            else:
                #executed only once, for the last block of the file
                block = data if not eof else self.padding_scheme.apply(data)
                if len(block) == self.block_size:
                    self.cipher_block = self.cipher.encrypt_block(
                        self._xor(block, self.cipher_block)
                    )
                elif len(block) == 2 * self.block_size:
                    last_block = self.cipher.encrypt_block(
                        self._xor(block[:self.block_size], self.cipher_block)
                    )
                    #This will append an entire block of padding (??)
                    self.cipher_block = self.cipher.encrypt_block(
                        self._xor(block[self.block_size:], last_block)
                    )
                    #set the cipher_block variable to be last block of real data
                    #prepended to the extra block of padding
                    self.cipher_block = last_block + self.cipher_block
                else:
                    raise Exception("Padding error: Padding scheme returned " +
                        "data that is not a multiple of the block length"
                    )
            yield self.cipher_block

    def decrypt(self, block_iterator):
        eof_iterator = eof_signal_iterator(block_iterator)

        #Always get the first 64 bytes of the data as IV. Even if it was already
        #supplied on the command line
        self.cipher_block, eof = next(eof_iterator)

        for data, eof in eof_iterator:
            plaintext = self._xor(
                self.cipher.decrypt_block(data), self.cipher_block
            )
            self.cipher_block = data
            block = plaintext if not eof else \
                self.padding_scheme.remove(plaintext)
            yield block

"""
CTR (counter) mode implemented by Niklas Mollenhauer <https://github.com/nikeee>.

For more information, visit https://en.wikipedia.org/wiki/Block_cipher_mode_of_operation#Counter_(CTR)
"""
class CTR(ModeOfOperation):
    def __init__(self, cipher, nonce):
        super(CTR, self).__init__(cipher)
        self.nonce = nonce

    def _get_xor_block(self, counter):

        # len(nonce + counter) should be equal to the block size
        # Since len(nonce) is block_size/2, len(counter) should also be block_size/2 (and therefore, len(nonce))
        counter_bytes = counter.to_bytes(len(self.nonce), byteorder='big')

        nonce_and_counter = self.nonce + counter_bytes
        assert len(nonce_and_counter) == self.block_size, 'Nonce and counter must be the same size as the block size.'

        return self.cipher.encrypt_block(nonce_and_counter)

    def encrypt(self, block_iterator):

        counter = 0
        eof_iterator = eof_signal_iterator(block_iterator)

        for data, eof in eof_iterator:

            xor_block = self._get_xor_block(counter)

            if eof and len(data) < self.block_size:
                xor_block = xor_block[:len(data)]

            ciphertext = self._xor(data, xor_block)
            counter += 1

            yield ciphertext

    def decrypt(self, block_iterator):
        # Decryption actually performs the same steps as encryption.
        # We also don't have to remove any padding. Therefore, we can just use the encryption procedure.
        return self.encrypt(block_iterator)


"""
GCM (Galois Counter Mode) mode implemented by Chris Baish <https://github.com/ChrisBaish>
Much of the code was reused from Niklas Mollenhaue's CTR class above. Any ensuing errors are mine.

Rather than just returning the cyphertext we need the authentication information as well
Therefore the output format is:
1. Header (1 cipher block)
2. Ciphertext (Unknown number of cipher blocks)
3. GMAC code (1 cipher block)

"""
class GCM(ModeOfOperation):
    def __init__(self, cipher, nonce, header):
        super(GCM, self).__init__(cipher)
        self.nonce = nonce
        self.header = header

    def _get_xor_block(self, counter):

        # len(nonce + counter) should be equal to the block size
        # Since len(nonce) is block_size/2, len(counter) should also be block_size/2 (and therefore, len(nonce))
        counter_bytes = counter.to_bytes(len(self.nonce), byteorder='big')

        nonce_and_counter = self.nonce + counter_bytes
        assert len(nonce_and_counter) == self.block_size, 'Nonce and counter must be the same size as the block size.'

        return self.cipher.encrypt_block(nonce_and_counter)

    def encrypt(self, block_iterator):
        bits_per_byte = 8
        num_bits = bits_per_byte * self.block_size

        ek_nonce = GP(num_bits, int.from_bytes(self._get_xor_block(0), "little"))
        counter = 1

        assert len(self.header) <= self.block_size, "Header must be fit in a single block"
        A = GP(num_bits, int.from_bytes(self.header, "little"))

        header_bytes = int.from_bytes(self.header, "little").to_bytes(self.block_size, "little")
        yield header_bytes

        zero = 0
        Ek_0_bytes = self.cipher.encrypt_block(zero.to_bytes(self.cipher.block_size, "little"))
        Ek_0 = GP(num_bits, int.from_bytes(Ek_0_bytes, "little"))

        rolling_polynomial = A.mult(Ek_0)

        eof_iterator = eof_signal_iterator(block_iterator)

        for data, eof in eof_iterator:

            xor_block = self._get_xor_block(counter)

            ciphertext = self._xor(data, xor_block)
            counter += 1

            C = GP(num_bits, int.from_bytes(ciphertext, "little"))
            rolling_polynomial = rolling_polynomial.xor(C).mult(Ek_0)


            yield ciphertext

        extra_block = len(self.header) << (num_bits // 2)
        extra_block += counter
        extra_block_gp = GP(num_bits, extra_block)
        rolling_polynomial = rolling_polynomial.xor(extra_block_gp).mult(Ek_0)

        gmac = rolling_polynomial.xor(ek_nonce)
        yield gmac.intval().to_bytes(self.block_size, "little")

    def decrypt(self, block_iterator):
        # This is similar to encryption, but we check the gmac rather than generate it.
        bits_per_byte = 8
        num_bits = bits_per_byte * self.block_size

        ek_nonce = GP(num_bits, int.from_bytes(self._get_xor_block(0), "little"))
        counter = 1

        eof_iterator = eof_signal_iterator(block_iterator)

        (header_bytes, b) = next(eof_iterator)
        assert not b, "File contained only 1 block"

        A = GP(num_bits, int.from_bytes(header_bytes, "little"))

        zero = 0
        Ek_0_bytes = self.cipher.encrypt_block(zero.to_bytes(self.cipher.block_size, "little"))
        Ek_0 = GP(num_bits, int.from_bytes(Ek_0_bytes, "little"))

        rolling_polynomial = A.mult(Ek_0)

        for ciphertext, eof in eof_iterator:
            if eof:
                break

            xor_block = self._get_xor_block(counter)

            data = self._xor(ciphertext, xor_block)
            counter += 1

            C = GP(num_bits, int.from_bytes(ciphertext, "little"))
            rolling_polynomial = rolling_polynomial.xor(C).mult(Ek_0)


            yield data

        extra_block = len(self.header) << (num_bits // 2)
        extra_block += counter
        extra_block_gp = GP(num_bits, extra_block)
        rolling_polynomial = rolling_polynomial.xor(extra_block_gp).mult(Ek_0)

        gmac = rolling_polynomial.xor(ek_nonce)
        gmac_bytes = gmac.intval().to_bytes(self.block_size, "little")

        if gmac_bytes == ciphertext:
            print("Message verified correctly")
        else:
            print("Message not verified")
