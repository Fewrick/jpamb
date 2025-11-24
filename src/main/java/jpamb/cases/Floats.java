package jpamb.cases;

import jpamb.utils.Case;

public class Floats {

  @Case("(0.0) -> ok")
  @Case("(-1.5) -> ok")
  public static void nonNegativeFloat(float input) {
    assert input >= 0.0f : "input must be non-negative";
  }

  @Case("(3.14) -> ok")
  @Case("(2.71) -> assertion error")
  public static void floatGreaterThanThree(float input) {
    assert input > 3.0f : "input must be greater than 3.0";
  }

  @Case("(1.0) -> ok")
  @Case("(0.0) -> assertion error")
  public static void floatIsPositive(float input) {
    assert input > 0.0f : "input must be positive";
  }
}