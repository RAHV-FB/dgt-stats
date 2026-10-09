/*
 * The crash-severity calculator's arithmetic, separate from its page so that it can be tested
 * against the Python model (tests/test_severity_engine.py runs it under Node).
 *
 * It reads the exported model (reports/models/severity_model.json, copied to
 * site/models/severity_model.json) and, for a scenario, builds the same 0/1 design vector as
 * dgt_stats.severity_model.design_matrix, the predicted probability expit(x'b) and its 95%
 * interval expit(x'b +- z sqrt(x'Vx)), z the normal quantile of a two-sided 95% interval.
 * Nothing here is estimated: every number comes from the exported coefficients and covariance.
 * The probability is conditional: the share that were fatal among recorded crashes with a death
 * or serious injury like the scenario, not the chance of a crash or of a death on a trip.
 */
(function (root, factory) {
  "use strict";
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.SeverityEngine = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var Z = 1.959964;
  // "4+" means four or more: no upper bound (dgt_stats.severity_model.UNIT_COUNTS).
  var UNITS = { "1": 1, "2": 2, "3": 3, "4+": Infinity };
  // The rules a scenario must not break (dgt_stats.severity_model.ERRORS): the crash itself, and
  // conditions that cannot occur together. predict and compare refuse a scenario that breaks one.
  var ERROR_RULES = {
    at_least_one_user: true,
    units_cover_users: true,
    pedestrian_struck_needs_pedestrian: true,
    heavy_rain_on_dry_surface: true,
    lighting_outside_hours: true
  };
  // Time bands that hold all year in Catalonia (dgt_stats.severity_model.DAYLIGHT and the two
  // bands after it): no daylight before 06:00 or from 22:00; only daylight from 10:00 to 13:59.
  var DAYLIGHT = ["day", "overcast"];
  var HOURS_WITHOUT_DAYLIGHT = ["00-05", "22-23"];
  var HOURS_OF_DAYLIGHT_ONLY = ["10-13"];

  function expit(z) {
    return 1 / (1 + Math.exp(-z));
  }

  function create(model) {
    var columns = model.columns;
    var coef = model.coefficients;
    var k = columns.length;
    var index = {};
    columns.forEach(function (name, i) { index[name] = i; });

    // The covariance is exported as its lower triangle, row by row.
    var cov = new Array(k);
    var position = 0;
    for (var i = 0; i < k; i++) {
      cov[i] = new Float64Array(k);
      for (var j = 0; j <= i; j++) {
        cov[i][j] = model.covariance_lower[position];
        position += 1;
      }
    }
    for (i = 0; i < k; i++) {
      for (j = i + 1; j < k; j++) cov[i][j] = cov[j][i];
    }

    var roads = {};
    model.inputs.road.levels.forEach(function (level) { roads[level.value] = level; });
    var provinces = {};
    model.inputs.province.levels.forEach(function (level) { provinces[level.value] = true; });
    var categorical = Object.keys(model.inputs).filter(function (name) {
      return model.inputs[name].type === "categorical" && name !== "road";
    });
    var users = model.inputs.users.levels.map(function (level) { return level.value; });

    function zoneOf(road) {
      if (!roads[road]) throw new Error("unknown road: " + road);
      return roads[road].zone;
    }

    function ticked(scenario) {
      return users.filter(function (user) { return Boolean(scenario[user]); });
    }

    // The indices of the design vector's ones (every entry is 0 or 1).
    function design(scenario) {
      var zone = zoneOf(scenario.road);
      var ones = [];
      function set(name) {
        if (Object.prototype.hasOwnProperty.call(index, name)) ones.push(index[name]);
      }
      if (!provinces[scenario.province]) throw new Error("unknown province: " + scenario.province);
      set("zone=" + zone);
      set("zone_province=" + zone + "|" + scenario.province);
      set("road=" + scenario.road);
      // "all:" columns are common to every zone; "<zone>:" columns, present only when the model
      // lets effects differ by zone, are the departure on that zone's roads.
      categorical.forEach(function (name) {
        var value = String(scenario[name]);
        var known = model.inputs[name].levels.some(function (level) { return level.value === value; });
        if (!known) throw new Error("unknown " + name + ": " + value);
        set("all:" + name + "=" + value);
        set(zone + ":" + name + "=" + value);
      });
      users.forEach(function (user) {
        if (scenario[user]) {
          set("all:" + user);
          set(zone + ":" + user);
        }
      });
      ones.sort(function (a, b) { return a - b; });
      return ones;
    }

    // The error rules a scenario breaks, in the order check lists them.
    function errorsOf(scenario) {
      var chosen = ticked(scenario);
      var units = UNITS[String(scenario.units)];
      var broken = [];
      if (chosen.length === 0) broken.push("at_least_one_user");
      if (units < chosen.length) broken.push("units_cover_users");
      if (scenario.crash_type === "pedestrian_struck" && !scenario.pedestrian) {
        broken.push("pedestrian_struck_needs_pedestrian");
      }
      if (scenario.weather === "heavy_rain_snow" && scenario.surface === "dry") {
        broken.push("heavy_rain_on_dry_surface");
      }
      var hour = String(scenario.hour);
      var daylight = DAYLIGHT.indexOf(String(scenario.lighting)) >= 0;
      if ((HOURS_WITHOUT_DAYLIGHT.indexOf(hour) >= 0 && daylight) ||
          (HOURS_OF_DAYLIGHT_ONLY.indexOf(hour) >= 0 && !daylight)) {
        broken.push("lighting_outside_hours");
      }
      return broken;
    }

    function refuse(scenario) {
      var broken = errorsOf(scenario);
      if (broken.length) throw new Error("refused scenario: " + broken.join(", "));
    }

    function predict(scenario) {
      refuse(scenario);
      var ones = design(scenario);
      var logit = 0;
      var variance = 0;
      for (var a = 0; a < ones.length; a++) {
        logit += coef[ones[a]];
        for (var b = 0; b < ones.length; b++) variance += cov[ones[a]][ones[b]];
      }
      var se = Math.sqrt(Math.max(variance, 0));
      return {
        probability: expit(logit),
        low: expit(logit - Z * se),
        high: expit(logit + Z * se),
        logit: logit,
        se: se
      };
    }

    // The first scenario against the second: ratio and difference of the predicted fatal shares,
    // each with a 95% delta-method interval (dgt_stats.severity_model.compare_exported).
    function compare(first, second) {
      refuse(first);
      refuse(second);
      var a = design(first);
      var b = design(second);
      var pa = predict(first).probability;
      var pb = predict(second).probability;
      var ratioGradient = {};
      var differenceGradient = {};
      a.forEach(function (i) {
        ratioGradient[i] = (ratioGradient[i] || 0) + (1 - pa);
        differenceGradient[i] = (differenceGradient[i] || 0) + pa * (1 - pa);
      });
      b.forEach(function (i) {
        ratioGradient[i] = (ratioGradient[i] || 0) - (1 - pb);
        differenceGradient[i] = (differenceGradient[i] || 0) - pb * (1 - pb);
      });
      function quadratic(gradient) {
        var keys = Object.keys(gradient).map(Number);
        var total = 0;
        for (var u = 0; u < keys.length; u++) {
          for (var v = 0; v < keys.length; v++) {
            total += gradient[keys[u]] * cov[keys[u]][keys[v]] * gradient[keys[v]];
          }
        }
        return Math.sqrt(Math.max(total, 0));
      }
      var logRatio = Math.log(pa / pb);
      var seRatio = quadratic(ratioGradient);
      var seDifference = quadratic(differenceGradient);
      return {
        ratio: pa / pb,
        ratio_low: Math.exp(logRatio - Z * seRatio),
        ratio_high: Math.exp(logRatio + Z * seRatio),
        difference: pa - pb,
        difference_low: pa - pb - Z * seDifference,
        difference_high: pa - pb + Z * seDifference
      };
    }

    function similar(scenario) {
      var key = [
        zoneOf(scenario.road),
        scenario.crash_type,
        ticked(scenario).slice().sort().join("+") || "none",
        String(scenario.units)
      ].join("|");
      var found = model.support[key];
      return { key: key, crashes: found ? found[0] : 0, fatal: found ? found[1] : 0 };
    }

    // Rule ids broken by a scenario, as dgt_stats.severity_model.check_scenario, plus the two
    // warnings that need the training counts: few similar crashes in the zone, and an input level
    // rarely or never recorded on the chosen road.
    function check(scenario) {
      var chosen = ticked(scenario);
      var units = UNITS[String(scenario.units)];
      var broken = errorsOf(scenario);
      if (model.collision_types.indexOf(scenario.crash_type) >= 0 && units === 1) {
        broken.push("collision_with_one_unit");
      }
      if (chosen.length === 1 && chosen[0] === "pedestrian") broken.push("pedestrian_without_vehicle");
      // Roads through towns get the average instead of an estimate only when the published model
      // was chosen that way (model.through_town, dgt_stats.severity_model.select).
      if (model.through_town === "average" && zoneOf(scenario.road) === "through_town") {
        broken.push("through_town");
      }
      var errors = broken.filter(function (id) { return ERROR_RULES[id]; });
      var warnings = broken.filter(function (id) { return !ERROR_RULES[id]; });
      var rare = [];
      if (errors.length === 0) {
        var threshold = 20;
        model.rules.forEach(function (rule) { if (rule.id === "few_similar") threshold = rule.threshold; });
        if (similar(scenario).crashes < threshold) warnings.push("few_similar");
        var road = String(scenario.road);
        categorical.forEach(function (name) {
          var count = model.level_support[road + "|" + name + "=" + String(scenario[name])] || 0;
          if (count < threshold) rare.push(name);
        });
        chosen.forEach(function (user) {
          var count = model.level_support[road + "|" + user] || 0;
          if (count < threshold) rare.push(user);
        });
        if (rare.length) warnings.push("rare_level");
      }
      return { errors: errors, warnings: warnings, rare: rare };
    }

    function levels(name) {
      return model.inputs[name].levels.map(function (level) { return level.value; });
    }

    return {
      design: design,
      predict: predict,
      compare: compare,
      check: check,
      similar: similar,
      zoneOf: zoneOf,
      levels: levels,
      daylight: DAYLIGHT.slice()
    };
  }

  return { create: create, expit: expit };
});
