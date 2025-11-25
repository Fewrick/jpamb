package jpamb.cases;

import jpamb.utils.Case;

public class Strings {
  @Case("(\"\") -> assertion error")
  @Case("(\"PA\") -> ok")
  public static void nonEmptyString(String input) {
    assert input != null : "input must not be null";
    assert input.length() > 0 : "input must not be empty";
  }

  @Case("(\"HELLO\") -> ok")
  @Case("(\"hello\") -> assertion error")
  public static void stringIsUppercase(String input) {
    assert input != null : "input must not be null";
    assert input.equals(input.toUpperCase()) : "input must be uppercase";
  }
  @Case("(\"ab\") -> assertion error")
  @Case("(\"abc\") -> ok")
  @Case("(\"abcd\") -> ok")
  public static void atLeastThreeChars(String input) {
      assert input != null : "input must not be null";
      assert input.length() >= 3 : "input must have at least 3 characters";
  }
  @Case("(\"hello\") -> ok")
  @Case("(\"world\") -> assertion error")
  public static void startsWithH(String input) {
      assert input != null : "input must not be null";
      assert input.length() > 0 : "input must not be empty";
      assert input.charAt(0) == 'h' : "input must start with 'h'";
  }
  @Case("() -> assertion error")
  @Case("(\"ProgramAnalysis\") -> ok")
  public static void spellsExactlyProgramAnalysis(String input) {
      assert input != null : "input must not be null";
      assert input.equals("ProgramAnalysis") : "string does not match 'ProgramAnalysis'";
  }
}