


""" Class to do arithmatic over GF(2^n) polynomials

* This is not the most efficient way to do it, but aims to be conceptually simple.
* Standard caveats about not being suitible for real world cryptography apply.

"""

# Irreducible polynomials taken from https://www.hpl.hp.com/techreports/98/HPL-98-135.pdf
# I have included a 0 in all of them to represent the +1, which is omitted from the table in the link.
irreducible_polynomials = {
    8   : [8, 4, 3, 1, 0],
    64  : [64, 4, 3, 1, 0],
    128 : [128, 7, 2, 1, 0],
    256 : [256, 10, 5, 2, 0],
    512 : [512, 8, 5, 2, 0]
}

class GaloisPolynomial():
    def __init__(self, num_bits, initial_value=0, irreducible_polynomial=[]):
        if (irreducible_polynomial == []):
            assert(num_bits in irreducible_polynomials.keys())
            self.irr_pol = irreducible_polynomials[num_bits]
        else:
            self.irr_pol = irreducible_polynomial

        self.length = num_bits
        self.bits = [0 for _ in range(num_bits)]
        assert(initial_value >= 0)
        assert(max(self.irr_pol) == self.length)

        i = num_bits - 1
        while initial_value > 0:
            assert(i >= 0)
            self.bits[i] = initial_value % 2
            i -= 1
            initial_value = initial_value >> 1

    def intval(self):
        return int(''.join([f'{i}' for i in self.bits]), 2)

    def xor(self, other):
        assert(isinstance(other, GaloisPolynomial))
        assert(self.length == other.length)
        output = GaloisPolynomial(self.length, 0, self.irr_pol)
        for i in range(self.length):
            output.bits[i] = self.bits[i] ^ other.bits[i]
        return output

    def mult(self, other):
        assert(isinstance(other, GaloisPolynomial))
        assert(self.length == other.length)

        shifted_vals = []
        for shift in range(self.length):
            index = self.length - 1 - shift # The lists are all smallest on the right
            if other.bits[index] == 1:
                shifted_val = [0 for _ in range(self.length - shift)] + self.bits + [0 for _ in range(shift)]
                shifted_vals.append(shifted_val)

        expected_length = self.length * 2
        for sv in shifted_vals:
            assert(len(sv) == expected_length)

        intermediate_polynomial = []
        for i in range(expected_length):
            sum = 0
            for sv in shifted_vals:
                sum += sv[i]
            intermediate_polynomial.append(sum % 2)

        ip_len = self.length + 1
        irr_pol_list = [0 for _ in range(ip_len)]
        for index in self.irr_pol:
            irr_pol_list[ip_len - 1 - index] = 1

        for i in range(expected_length - self.length):
            if intermediate_polynomial[i] == 1:
                shifted_irr_pol = [0 for _ in range(i)] + irr_pol_list + [0 for _ in range(expected_length - ip_len - i)]
                assert(len(shifted_irr_pol) == expected_length)
                for i in range(expected_length):
                    intermediate_polynomial[i] = intermediate_polynomial[i] ^ shifted_irr_pol[i]
        assert(intermediate_polynomial[:expected_length - self.length] == [0 for _ in range(expected_length - self.length)])
        output_polynomial = intermediate_polynomial[expected_length - self.length:]

        output = GaloisPolynomial(self.length, 0, self.irr_pol)
        output.bits = output_polynomial
        return output
