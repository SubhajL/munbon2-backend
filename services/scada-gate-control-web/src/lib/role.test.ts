import { describe, expect, test } from "vitest";
import { canCommand, mapAppRole, userFromToken, type AppRole } from "./role";

const fakeJwt = (payload: object): string => {
  const b64url = (obj: object) =>
    Buffer.from(JSON.stringify(obj))
      .toString("base64")
      .replace(/\+/g, "-")
      .replace(/\//g, "_")
      .replace(/=+$/, "");
  return `${b64url({ alg: "HS256" })}.${b64url(payload)}.sig`;
};

describe("mapAppRole", () => {
  test.each<[string[], AppRole]>([
    [["rid_admin"], "admin"],
    [["zone_manager"], "operator"],
    [["guest"], "viewer"],
    [["guest", "rid_admin"], "admin"],
  ])("%j -> %s", (roles, expected) => {
    expect(mapAppRole(roles)).toBe(expected);
  });
});

describe("canCommand", () => {
  test.each<[AppRole, boolean]>([
    ["viewer", false],
    ["operator", true],
    ["admin", true],
  ])("%s -> %s", (role, expected) => {
    expect(canCommand(role)).toBe(expected);
  });
});

describe("userFromToken", () => {
  test("extracts the email and mapped role from the access-token claims", () => {
    expect(
      userFromToken(
        fakeJwt({
          sub: "u",
          email: "op@rid.go.th",
          roles: ["zone_manager"],
          type: "access",
        }),
      ),
    ).toEqual({ email: "op@rid.go.th", role: "operator" });
  });

  test("falls back to a null email and viewer role when claims are missing or malformed", () => {
    expect(userFromToken(fakeJwt({ sub: "u", roles: ["rid_admin"] }))).toEqual({
      email: null,
      role: "admin",
    });
    expect(userFromToken(undefined)).toEqual({ email: null, role: "viewer" });
    expect(userFromToken("not-a-jwt")).toEqual({ email: null, role: "viewer" });
  });
});
