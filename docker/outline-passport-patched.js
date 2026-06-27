"use strict";

Object.defineProperty(exports, "__esModule", {
  value: true
});
exports.StateStore = void 0;
exports.getClientFromOAuthState = getClientFromOAuthState;
exports.getTeamFromContext = getTeamFromContext;
exports.getUserFromOAuthState = getUserFromOAuthState;
exports.parseState = parseState;
exports.request = request;
exports.startOAuthFlow = startOAuthFlow;
var _nodeCrypto = _interopRequireDefault(require("node:crypto"));
var _dateFns = require("date-fns");
var _types = require("../../shared/types");
var _domains = require("../../shared/utils/domains");
var _env = _interopRequireDefault(require("../env"));
var _models = require("../models");
var _redis = _interopRequireDefault(require("../storage/redis"));
var _errors = require("../errors");
var _crypto = require("./crypto");
var _fetch = _interopRequireDefault(require("./fetch"));
var _jwt = require("./jwt");
var _oauthState = require("./oauthState");
function _interopRequireDefault(e) { return e && e.__esModule ? e : { default: e }; }
function _defineProperty(e, r, t) { return (r = _toPropertyKey(r)) in e ? Object.defineProperty(e, r, { value: t, enumerable: !0, configurable: !0, writable: !0 }) : e[r] = t, e; }
function _toPropertyKey(t) { var i = _toPrimitive(t, "string"); return "symbol" == typeof i ? i : i + ""; }
function _toPrimitive(t, r) { if ("object" != typeof t || !t) return t; var e = t[Symbol.toPrimitive]; if (void 0 !== e) { var i = e.call(t, r || "default"); if ("object" != typeof i) return i; throw new TypeError("@@toPrimitive must return a primitive value."); } return ("string" === r ? String : Number)(t); }
const FLOW_QUERY_PARAM = "flow";
const OAUTH_CSRF_COOKIE = "oauth_csrf";
const OAUTH_INTENT_PREFIX = "oauth:intent:";
const OAUTH_INTENT_TTL_SECONDS = 10 * 60;
const ACTOR_SESSION_HASH_KEYLEN = 64;

/**
 * Middleware for OAuth start routes that bridges cookie scopes between custom
 * team domains and the apex (env.URL) where the OAuth callback always lands.
 *
 * The OAuth callback always lands on the apex domain, while a user's
 * `accessToken` session cookie may be host-scoped to a custom team domain. To
 * make the "connect a new auth provider while signed in" flow work from a
 * custom domain:
 *
 *   1. On a custom team domain — create a short-lived signed intent containing
 *      the original host and actor id, then bounce to the apex with it.
 *   2. On the apex — verify the signed intent and stash it on `ctx.state` so
 *      `StateStore.store` can fold it into the signed OAuth `state` parameter.
 *
 * Non-custom team subdomains skip the bounce because the start route can read
 * the host-scoped session and set the OAuth CSRF cookie on the base domain for
 * the apex callback. Self-hosted deployments have a single domain and pass
 * through.
 */
async function startOAuthFlow(ctx, next) {
  if (!_env.default.isCloudHosted) {
    return next();
  }
  const apex = new URL(_env.default.URL);
  const onApex = ctx.hostname === apex.hostname;
  const isCustom = (0, _domains.parseDomain)(ctx.hostname).custom;
  if (isCustom && !onApex) {
    const url = new URL(ctx.originalUrl, apex);
    const client = getClientFromInput(ctx);
    const actor = await getOAuthActor(ctx);
    const flow = (0, _oauthState.signOAuthIntent)({
      host: ctx.hostname,
      actorId: actor?.id,
      actorSessionHash: actor ? getActorSessionHash(actor) : undefined,
      client
    });
    url.searchParams.delete(FLOW_QUERY_PARAM);
    url.searchParams.set(FLOW_QUERY_PARAM, flow);
    await storeOAuthIntent(flow);
    return ctx.redirect(url.toString());
  }
  const flow = ctx.query[FLOW_QUERY_PARAM];
  if (onApex && typeof flow === "string" && flow) {
    try {
      const intent = (0, _oauthState.verifyOAuthIntent)(flow);
      if (await consumeOAuthIntent(flow)) {
        ctx.state.oauthIntent = intent;
      }
    } catch {
      // Invalid or expired intent — proceed without an actor.
      // The user can still complete the OAuth flow as a fresh sign-in.
    }
  }
  return next();
}

/**
 * Passport OAuth state store backed by signed state and a CSRF nonce cookie.
 */
class StateStore {
  constructor() {
    let pkce = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : false;
    this.pkce = pkce;
    _defineProperty(this, "key", "state");
    _defineProperty(this, "store", (ctx, verifierOrCallback, _state, _meta, cb) => {
      const context = getKoaContext(ctx);
      const csrfNonce = _nodeCrypto.default.randomBytes(16).toString("hex");

      // Note parameters are based on whether PKCE is in use or not, this is parameters
      // of how the underlying library is architected, see:
      // https://github.com/jaredhanson/passport-oauth2/blob/be9bf58cee75938c645a9609f0cc87c4c724e7c8/lib/strategy.js#L289-L298
      const callback = typeof verifierOrCallback === "function" ? verifierOrCallback : cb;
      if (!callback) {
        throw (0, _errors.InternalError)("Callback is required");
      }
      const codeVerifier = typeof verifierOrCallback === "function" ? undefined : verifierOrCallback;

      // We expect host to be a team subdomain, custom domain, or apex domain
      // that is passed via query param from the auth provider component.
      const client = context.state.oauthIntent?.client ?? getClientFromInput(context);
      const host = context.state.oauthIntent?.host ?? context.query.host?.toString() ?? (0, _domains.parseDomain)(context.hostname).host;
      const actorId = context.state.oauthIntent?.actorId ?? getAuthenticatedUserId(context);
      const actorSessionHash = context.state.oauthIntent?.actorSessionHash ?? getAuthenticatedUserSessionHash(context);
      const state = (0, _oauthState.signOAuthState)({
        host,
        actorId,
        actorSessionHash,
        client,
        codeVerifier,
        nonceHash: (0, _oauthState.hashOAuthStateNonce)(csrfNonce)
      });
      context.cookies.set(OAUTH_CSRF_COOKIE, csrfNonce, {
        httpOnly: true,
        sameSite: "lax",
        secure: false,
        expires: (0, _dateFns.addMinutes)(new Date(), 10),
        domain: (0, _domains.getCookieDomain)(context.hostname, _env.default.isCloudHosted)
      });
      callback(null, state);
    });
    _defineProperty(this, "verify", (ctx, providedToken, callback) => {
      const context = getKoaContext(ctx);
      const csrfNonce = context.cookies.get(OAUTH_CSRF_COOKIE);
      context.cookies.set(OAUTH_CSRF_COOKIE, "", {
        httpOnly: true,
        sameSite: "lax",
        secure: false,
        expires: (0, _dateFns.subMinutes)(new Date(), 1),
        domain: (0, _domains.getCookieDomain)(context.hostname, _env.default.isCloudHosted)
      });
      let state;
      try {
        state = (0, _oauthState.verifyOAuthState)(providedToken);
      } catch (err) {
        return callback(err, false, providedToken);
      }
      if (!(0, _crypto.safeEqual)((0, _oauthState.hashOAuthStateNonce)(csrfNonce ?? ""), state.nonceHash)) {
        return callback((0, _errors.OAuthStateMismatchError)("OAuth CSRF nonce mismatched"), false, providedToken);
      }
      context.state.oauthState = state;

      // @ts-expect-error Type in library is wrong
      callback(null, state.codeVerifier ?? true, providedToken);
    });
  }
}
exports.StateStore = StateStore;
async function request(method, endpoint, accessToken) {
  const response = await (0, _fetch.default)(endpoint, {
    method,
    allowPrivateIPAddress: true,
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json"
    }
  });
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch (_err) {
    throw (0, _errors.InternalError)(`Failed to parse response from ${endpoint}. Expected JSON, got: ${text}`);
  }
}

/**
 * Parses the state string into its components.
 *
 * @param state The state string
 * @returns An object containing the parsed components, if valid.
 */
function parseState(state) {
  try {
    return (0, _oauthState.verifyOAuthState)(state);
  } catch {
    return undefined;
  }
}

/**
 * Returns the client type from the context if available. Used to redirect
 * the user back to the correct client after the OAuth flow.
 *
 * @param ctx The Koa context
 * @returns The client type, defaults to Client.Web
 */
function getClientFromOAuthState(ctx) {
  const context = getKoaContext(ctx);
  const client = context.state.oauthState?.client;
  return client === _types.Client.Desktop ? _types.Client.Desktop : _types.Client.Web;
}

/**
 * Returns the actor referenced by verified OAuth state, if available. This is
 * used to restore the originating user during the OAuth flow when connecting
 * additional providers to an existing team.
 *
 * @param ctx The Koa context
 * @returns The actor if available, otherwise undefined
 */
async function getUserFromOAuthState(ctx) {
  const context = getKoaContext(ctx);
  const state = context.state.oauthState;
  if (!state?.actorId || !state.actorSessionHash) {
    return undefined;
  }
  const user = await _models.User.scope("withTeam").findByPk(state.actorId);
  if (!user) {
    return undefined;
  }
  if (!(0, _crypto.safeEqual)(getActorSessionHash(user), state.actorSessionHash)) {
    return undefined;
  }
  return user;
}
/**
 * Infers the team from the context based on the hostname or OAuth state.
 *
 * @param ctx The Koa context
 * @param options Options for determining the team
 * @returns The inferred team or undefined if not found
 */
async function getTeamFromContext(ctx) {
  let options = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {
    includeOAuthState: true
  };
  const context = getKoaContext(ctx);
  // "domain" is the domain the user came from when attempting auth
  // we use it to infer the team they intend on signing into
  const includeOAuthState = options.includeOAuthState ?? true;
  const state = includeOAuthState ? context.state.oauthState ?? context.state.oauthIntent : undefined;
  const queryHost = options.includeHostQueryParam && typeof context.query.host === "string" ? context.query.host : undefined;
  const host = state?.host ?? queryHost ?? context.hostname;
  const domain = (0, _domains.parseDomain)(host);
  let team;
  if (!_env.default.isCloudHosted) {
    if (_env.default.ENVIRONMENT === "test") {
      team = await _models.Team.findByDomain(_env.default.URL);
    } else {
      team = await _models.Team.findOne({
        order: [["createdAt", "DESC"]]
      });
    }
  } else if (context.state?.rootShare) {
    team = await _models.Team.findByPk(context.state.rootShare.teamId);
  } else if (domain.custom) {
    team = await _models.Team.findByDomain(domain.host);
  } else if (domain.teamSubdomain) {
    team = await _models.Team.findBySubdomain(domain.teamSubdomain);
  }
  return team;
}
function getClientFromInput(ctx) {
  const clientInput = ctx.query.client?.toString();
  return clientInput === _types.Client.Desktop ? _types.Client.Desktop : _types.Client.Web;
}
function getAuthenticatedUser(ctx) {
  return ctx.state.auth && "user" in ctx.state.auth ? ctx.state.auth.user : undefined;
}
function getAuthenticatedUserId(ctx) {
  return getAuthenticatedUser(ctx)?.id;
}
function getAuthenticatedUserSessionHash(ctx) {
  const user = getAuthenticatedUser(ctx);
  return user ? getActorSessionHash(user) : undefined;
}
async function getOAuthActor(ctx) {
  const authenticatedUser = getAuthenticatedUser(ctx);
  if (authenticatedUser) {
    return authenticatedUser;
  }
  const accessToken = ctx.cookies.get("accessToken");
  if (!accessToken) {
    return undefined;
  }
  try {
    const {
      user
    } = await (0, _jwt.getUserForJWT)(accessToken);
    return user;
  } catch {
    return undefined;
  }
}
function getActorSessionHash(user) {
  return _nodeCrypto.default.scryptSync(user.jwtSecret, `oauth-actor-session:${_env.default.SECRET_KEY}:${user.id}`, ACTOR_SESSION_HASH_KEYLEN).toString("hex");
}
async function storeOAuthIntent(token) {
  await _redis.default.defaultClient.set(getOAuthIntentKey(token), "1", "EX", OAUTH_INTENT_TTL_SECONDS);
}
async function consumeOAuthIntent(token) {
  const result = await _redis.default.defaultClient.getdel(getOAuthIntentKey(token));
  return result === "1";
}
function getOAuthIntentKey(token) {
  return `${OAUTH_INTENT_PREFIX}${(0, _crypto.hash)(token)}`;
}
function getKoaContext(ctx) {
  return ctx.ctx ?? ctx;
}