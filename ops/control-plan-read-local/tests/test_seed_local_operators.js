"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const { seedLocalOperator } = require("../seed-local-operators");

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
      state.roles = [role];
      return role;
    },
  };
  const userRepository = {
    findOne: async ({ where }) =>
      state.users.find((user) => user.email === where.email) ?? null,
    create: (values) => Object.assign(new User(), values),
    save: async (user) => {
      await user.hashPassword();
      state.users = [user];
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
