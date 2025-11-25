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
  @Case("(5, true) -> pass")
  @Case("(5, false) -> fail")
  @Case("(15, false) -> pass")
  @Case("(15, true) -> excellent")
  public static String examResult(int score, boolean extraCredit) {
      if (extraCredit) {
          score = score + 10;
      }
      if (score >= 20) {
          return "excellent";
      }
      if (score >= 10) {
          return "pass";
      }
      return "fail";
  }

  @Case("(100, 50) -> first wins")
  @Case("(50, 100) -> second wins")
  @Case("(75, 75) -> tie")
  public static String compareScores(int score1, int score2) {
      if (score1 > score2) {
          return "first wins";
      }
      if (score2 > score1) {
          return "second wins";
      }
      return "tie";
  }

  @Case("(5, 10, 3) -> medium")
  @Case("(15, 8, 12) -> high")
  @Case("(2, 1, 1) -> low")
  public static String averageCategory(int a, int b, int c) {
      int avg = (a + b + c) / 3;
      if (avg < 5) {
          return "low";
      }
      if (avg < 10) {
          return "medium";
      }
      return "high";
  }
}
