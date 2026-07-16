const gateLevels = require("../src/config/gate-levels.json");

describe("RMC SCADA station ids", () => {
  test("use the V3 subtree rooted at M(0,0;2,0)", () => {
    const aliases = [
      "RMC1",
      "RMC2",
      "RMC3",
      "RMC4",
      "RMC5",
      "RMC6",
      "4L-RMC1",
      "4L-RMC2",
      "4L-RMC3",
      "4L-RMC5",
      "4L-RMC6",
      "4l-RMC4",
      "RMC3-B",
    ];
    const stationCodes = Object.fromEntries(
      aliases.map((alias) => [
        alias,
        gateLevels.automatic_gates[alias].station_code.replaceAll(" ", ""),
      ]),
    );

    expect(stationCodes).toEqual({
      RMC1: "M(0,0;2,0)",
      RMC2: "M(0,0;2,1)",
      RMC3: "M(0,0;2,0;1,0)",
      RMC4: "M(0,0;2,2)",
      RMC5: "M(0,0;2,3)",
      RMC6: "M(0,0;2,4)",
      "4L-RMC1": "M(0,0;2,1;1,0)",
      "4L-RMC2": "M(0,0;2,1;1,1)",
      "4L-RMC3": "M(0,0;2,1;1,2)",
      "4L-RMC5": "M(0,0;2,1;1,3)",
      "4L-RMC6": "M(0,0;2,1;1,3)",
      "4l-RMC4": "M(0,0;2,1;1,2;1,0)",
      "RMC3-B": "M(0,0;2,0;1,0;1,0)",
    });
  });
});
