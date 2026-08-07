"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { seedLocalOperator, seedLocalUser } = require("../seed-local-operators");

class Role {}

class User {
  async hashPassword() {
    if (!this.password.startsWith("hashed:"))
      this.password = `hashed:${this.password}`;
  }
}

function dataSourceWithState(state) {
  const roleRepository = {
    findOne: async ({ where }) =>
      state.roles.find((role) => role.name === where.name) ?? null,
    create: (values) => Object.assign(new Role(), values),
    save: async (role) => {
      // Roles accumulate: operator and field_team must be able to coexist, or a
      // two-role seed would silently clobber the first.
      state.roles = [
        ...state.roles.filter((existing) => existing.name !== role.name),
        role,
      ];
      return role;
    },
  };
  const userRepository = {
    findOne: async ({ where }) =>
      state.users.find((user) => user.email === where.email) ?? null,
    create: (values) => Object.assign(new User(), values),
    save: async (user) => {
      await user.hashPassword();
      state.users = [
        ...state.users.filter((existing) => existing.email !== user.email),
        user,
      ];
      return user;
    },
  };
  return {
    getRepository: (entity) =>
      entity === Role ? roleRepository : userRepository,
  };
}

test("seedLocalOperator is idempotent, hashes password, and assigns only operator", async () => {
  const state = { roles: [], users: [] };
  const dataSource = dataSourceWithState(state);
  const input = {
    email: "operator@example.invalid",
    password: "Local-only1!",
    firstName: "Local",
    lastName: "Operator",
  };

  const first = await seedLocalOperator(dataSource, input, { Role, User });
  const second = await seedLocalOperator(dataSource, input, { Role, User });

  assert.deepEqual(first, { created: true, roleCreated: true });
  assert.deepEqual(second, { created: false, roleCreated: false });
  assert.equal(state.users[0].password, "hashed:Local-only1!");
  assert.deepEqual(
    state.users[0].roles.map((role) => role.name),
    ["operator"],
  );
  assert.equal(state.users[0].status, "active");
});

test("seedLocalOperator migrates the previous disposable email without duplicating users", async () => {
  const previous = Object.assign(new User(), {
    email: "operator@example.invalid",
    password: "hashed:Local-only1!",
    status: "active",
    roles: [],
  });
  const state = { roles: [], users: [previous] };

  const result = await seedLocalOperator(
    dataSourceWithState(state),
    {
      email: "operator@example.com",
      password: "Local-only1!",
      firstName: "Local",
      lastName: "Operator",
      previousEmails: ["operator@example.invalid"],
    },
    { Role, User },
  );

  assert.deepEqual(result, { created: false, roleCreated: true });
  assert.equal(state.users.length, 1);
  assert.equal(state.users[0].email, "operator@example.com");
  assert.equal(state.users[0].password, "hashed:Local-only1!");
});

test("seedLocalUser grants exactly the requested role and stays idempotent", async () => {
  const state = { roles: [], users: [] };
  const dataSource = dataSourceWithState(state);
  const input = {
    email: "field-team@example.invalid",
    password: "Local-only1!",
    firstName: "Local",
    lastName: "FieldTeam",
    roleName: "field_team",
  };

  const first = await seedLocalUser(dataSource, input, { Role, User });
  const second = await seedLocalUser(dataSource, input, { Role, User });

  assert.deepEqual(first, { created: true, roleCreated: true });
  assert.deepEqual(second, { created: false, roleCreated: false });
  assert.deepEqual(
    state.users[0].roles.map((role) => role.name),
    ["field_team"],
  );
  assert.equal(state.users[0].status, "active");
  assert.equal(state.users[0].password, "hashed:Local-only1!");
});

test("field_team is seeded WITHOUT inheriting operator rights", async () => {
  // The whole point of the field-team drill is that this user is denied. If the
  // seed granted `operator` too, the stage would prove nothing.
  const state = { roles: [], users: [] };
  const dataSource = dataSourceWithState(state);

  await seedLocalUser(
    dataSource,
    {
      email: "operator@example.invalid",
      password: "Local-only1!",
      firstName: "Local",
      lastName: "Operator",
      roleName: "operator",
    },
    { Role, User },
  );
  await seedLocalUser(
    dataSource,
    {
      email: "field-team@example.invalid",
      password: "Local-only1!",
      firstName: "Local",
      lastName: "FieldTeam",
      roleName: "field_team",
    },
    { Role, User },
  );

  const fieldTeam = state.users.find(
    (user) => user.email === "field-team@example.invalid",
  );
  const operator = state.users.find(
    (user) => user.email === "operator@example.invalid",
  );

  assert.deepEqual(
    fieldTeam.roles.map((role) => role.name),
    ["field_team"],
  );
  assert.deepEqual(
    operator.roles.map((role) => role.name),
    ["operator"],
  );
  assert.equal(state.roles.length, 2);
});
