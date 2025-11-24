package jpamb.cases;

import jpamb.utils.Case;

public class Branch {

    @Case("(\"a1b2c3\") -> ok")
    @Case("(\"a1b2c4\") -> assertion error")
    @Case("(\"11b2c3\") -> assertion error")
    @Case("(\"a1b2\") -> assertion error")
    public static void alternatingSum(String input) {
        // Expects pattern: Letter-Digit-Letter-Digit...
        // Also requires the sum of all digits to be exactly 6.
        if (input == null)
            assert false;

        int sum = 0;
        boolean expectLetter = true;

        for (int i = 0; i < input.length(); i++) {
            char c = input.charAt(i);
            if (expectLetter) {
                if (c >= '0' && c <= '9') {
                    assert false : "expected letter at index " + i;
                }
                expectLetter = false;
            } else {
                if (c >= '0' && c <= '9') {
                    sum += (c - '0');
                    expectLetter = true;
                } else {
                    assert false : "expected digit at index " + i;
                }
            }
        }

        if (sum == 6) {
            if (!expectLetter) {
                return;
            }
        }
        assert false : "invalid sum or incomplete sequence";
    }

    @Case("(\"PA02242\") -> ok")
    @Case("(\"PA02243\") -> assertion error")
    @Case("(\"PB02242\") -> assertion error")
    @Case("(\"PA0224\") -> assertion error")
    public static void fireTheNukes(String input) {
        // Format: "PA" + "02242"
        if (input == null)
            assert false;
        if (input.length() == 7) {
            if (input.charAt(0) == 'P' && input.charAt(1) == 'A') {
                String numberPart = input.substring(2);
                if (numberPart.equals("02242")) {
                    return;
                } else {
                    assert false : "invalid code number";
                }
            } else {
                assert false : "invalid code prefix";
            }
        } else {
            assert false : "invalid code length";
        }
    }

}
