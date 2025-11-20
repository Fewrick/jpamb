package jpamb.cases;

import jpamb.utils.*;
import static jpamb.utils.Tag.TagType.*;

public class Loops {

  @Case("() -> *")
  @Tag({ LOOP })
  public static void forever() {
    while (true) {
    }
  }

  @Case("() -> *")
  @Tag({ LOOP })
  public static void neverAsserts() {
    int i = 1;
    while (i > 0) {
    }
    assert false;
  }

  @Case("() -> *")
  @Tag({ LOOP })
  public static int neverDivides() {
    int i = 1;
    while (i > 0) {
    }
    return 0 / 0;
  }

  @Case("() -> assertion error")
  @Tag({ LOOP, INTEGER_OVERFLOW })
  public static void terminates() {
    short i = 0;
    while (i++ != 0) {
    }
    assert false;
  }

  @Case("(5) -> small")
  @Case("(10) -> medium")
  @Case("(20) -> large")
  public static String testMultipleBranches(int x) {
    if (x < 10) {
      return "small";
    }
    if (x < 20) {
      return "medium";
    }
    return "large";
  }

  @Case("(5) -> less")
  @Case("(10) -> equal")  
  @Case("(15) -> greater")
  public static String testEqual(int x) {
      if (x == 10) {
          return "equal";
      }
      if (x < 10) {
          return "less";
      }
      return "greater";
  }

  @Case("(5) -> not equal")
  @Case("(10) -> is ten")
  public static String testNotEqual(int x) {
      if (x != 10) {
          return "not equal";
      }
      return "is ten";
  }
  
  @Case("(15) -> ok")
  @Case("(5) -> too small")
  public static String testGreaterOrEqual(int x) {
      if (x >= 10) {
          return "ok";
      }
      return "too small";
  }

  @Case("(5) -> ok")
  @Case("(15) -> too big")
  public static String testLessOrEqual(int x) {
      if (x <= 10) {
          return "ok";
      }
      return "too big";
  }

}
