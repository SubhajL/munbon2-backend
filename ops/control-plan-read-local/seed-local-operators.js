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

const ROLE_PROFILES = {
  operator: {
    displayName: "Control Plan Operator",
    description: "Disposable local control-plan acceptance operator",
  },
  // Deliberately carries NO planning-depth rights: the write-UI stage proves
  // this principal is DENIED (roster/active 403, Submit not rendered). Granting
  // it anything more would make that drill prove nothing.
  field_team: {
    displayName: "Field Team",
    description: "Disposable local field-team acceptance user (no operator rights)",
  },
};

async function seedLocalUser(dataSource, input, entities = loadEntities()) {
  const roleName = input.roleName || "operator";
  const profile = ROLE_PROFILES[roleName];
  if (!profile) throw new Error("unknown_role_profile");
  const roleRepository = dataSource.getRepository(entities.Role);
  const userRepository = dataSource.getRepository(entities.User);
  let role = await roleRepository.findOne({ where: { name: roleName } });
  const roleCreated = role === null;
  if (roleCreated) {
    role = roleRepository.create({
      name: roleName,
      displayName: profile.displayName,
      description: profile.description,
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

async function seedLocalOperator(dataSource, input, entities = loadEntities()) {
  return seedLocalUser(dataSource, { ...input, roleName: "operator" }, entities);
}

async function main() {
  const email = process.env.MUNBON_OPERATOR_EMAIL;
  const password = process.env.MUNBON_OPERATOR_PASSWORD;
  if (!email || !password) throw new Error("operator_credentials_missing");
  const fieldTeamEmail = process.env.MUNBON_FIELD_TEAM_EMAIL;
  const fieldTeamPassword = process.env.MUNBON_FIELD_TEAM_PASSWORD;
  if (!fieldTeamEmail || !fieldTeamPassword) {
    throw new Error("field_team_credentials_missing");
  }
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
    const fieldTeam = await seedLocalUser(AppDataSource, {
      email: fieldTeamEmail,
      password: fieldTeamPassword,
      firstName: "Local",
      lastName: "FieldTeam",
      roleName: "field_team",
    });
    process.stdout.write(
      `PASS local_operator_seed created=${result.created} role_created=${result.roleCreated}\n`,
    );
    process.stdout.write(
      `PASS local_field_team_seed created=${fieldTeam.created} role_created=${fieldTeam.roleCreated}\n`,
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

module.exports = { seedLocalOperator, seedLocalUser };
