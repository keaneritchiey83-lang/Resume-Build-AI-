"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = require("express");
const team_controller_1 = require("../controllers/team.controller");
const auth_1 = require("../middleware/auth");
const router = (0, express_1.Router)();
router.use(auth_1.authenticate);
router.post('/', team_controller_1.createTeam);
router.get('/', team_controller_1.getTeams);
router.get('/:id', team_controller_1.getTeam);
router.put('/:id', team_controller_1.updateTeam);
router.delete('/:id', team_controller_1.deleteTeam);
router.post('/:id/members', team_controller_1.addMember);
router.delete('/:id/members/:userId', team_controller_1.removeMember);
router.get('/:id/members', team_controller_1.getMembers);
exports.default = router;
//# sourceMappingURL=team.routes.js.map