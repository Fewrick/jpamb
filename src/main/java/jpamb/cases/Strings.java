package jpamb.cases;

import jpamb.utils.Case;

public class Strings {
  @Case("(\"\") -> assertion error")
  @Case("(\"PA\") -> ok")
  public static void nonEmptyString(String input) {
    assert input != null : "input must not be null";
    assert input.length() > 0 : "input must not be empty";
  }
}