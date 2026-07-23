"use strict";

const path = require("node:path");

function loadEntities() {
  const repoRoot =
    process.env.MUNBON_REPO_ROOT || path.resolve(__dirname, "../..");
  return {
    Role: require(path.join(repoRoot, "services/auth/src/models/role.entity"))
      .Role,
    User: require(path.join(repoRoot, "services/auth/src/models/user.entity"))
      .User,
  };
}

async function seedLocalOperator(dataSource, input, entities = loadEntities()) {
  const roleRepository = dataSource.getRepository(entities.Role);
  const userRepository = dataSource.getRepository(entities.User);
  let role = await roleRepository.findOne({ where: { name: "operator" } });
  const roleCreated = role === null;
  if (roleCreated) {
    role = roleRepository.create({
      name: "operator",
      displayName: "Control Plan Operator",
      description: "Disposable local control-plan acceptance operator",
      isActive: true,
      isSystem: true,
      permissions: [],
    });
    role = await roleRepository.save(role);
  }

  let user = await userRepository.findOne({ where: { email: input.email } });
  if (user === null) {
    for (const previousEmail of input.previousEmails || []) {
      user = await userRepository.findOne({ where: { email: previousEmail } });
      if (user !== null) {
        user.email = input.email;
        break;
      }
    }
  }
  const created = user === null;
  if (created) {
    user = userRepository.create({
      email: input.email,
      password: input.password,
      firstName: input.firstName,
      lastName: input.lastName,
      userType: "government_official",
      status: "active",
      emailVerified: true,
      roles: [role],
    });
  } else {
    user.status = "active";
    user.roles = [role];
  }
  await userRepository.save(user);
  return { created, roleCreated };
}

async function main() {
  const email = process.env.MUNBON_OPERATOR_EMAIL;
  const password = process.env.MUNBON_OPERATOR_PASSWORD;
  if (!email || !password) throw new Error("operator_credentials_missing");
  const repoRoot =
    process.env.MUNBON_REPO_ROOT || path.resolve(__dirname, "../..");
  const { AppDataSource } = require(
    path.join(repoRoot, "services/auth/src/config/database"),
  );
  await AppDataSource.initialize();
  try {
    const result = await seedLocalOperator(AppDataSource, {
      email,
      password,
      firstName: "Local",
      lastName: "Operator",
      previousEmails: ["operator@example.invalid"],
    });
    process.stdout.write(
      `PASS local_operator_seed created=${result.created} role_created=${result.roleCreated}\n`,
    );
  } finally {
    await AppDataSource.destroy();
  }
}

if (require.main === module) {
  main().catch(() => {
    process.stderr.write("FAIL local_operator_seed\n");
    process.exitCode = 1;
  });
}

module.exports = { seedLocalOperator };
