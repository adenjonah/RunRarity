import joblib
from feature_extraction import calculate_features


def predict_rarity(polyline_str, model_path="polyline_model.pkl"):
    """
    Predict the rarity score for a given polyline using the trained model.
    :param polyline_str: Polyline string.
    :param model_path: Path to the trained model file.
    :return: Predicted rarity score.
    """
    # Load the trained model
    model = joblib.load(model_path)

    # Extract features from the polyline
    features = calculate_features(polyline_str)
    if features:
        feature_values = list(features.values())
        rarity_score = model.predict([feature_values])[0]
        return rarity_score
    else:
        return "Invalid polyline"


# Example usage
polyline = "}o~aHv|zgUGz@EdBCd@IbII|BGz@a@|A_@l@[Lw@Pc@COEuAo@_@[[QgB}Aa@a@cBoAk@g@oAaAg@Ym@k@cAg@kA}@gDsBa@]o@]w@q@]QaBe@yAWQWSoAMS_@IwAb@_Cb@o@@s@Hg@RcBTkAXMJMd@SXwAj@w@j@a@LSLu@z@gAhByA`De@~@wAlDm@fAcAnCYbAq@hBUx@oBlEc@r@cAjAe@x@c@`AyAtDWbAc@lAe@~@Wr@Sl@cBtG_@b@YFUP]n@Yt@m@rBS^Uh@O~@Y|@YjAUl@]fAm@bBa@~Ai@fBBAp@gCn@oB^yA`CwHd@iBv@_CPc@ZUp@[DCPa@t@eCpBoGdAkC\\iA`AgC`AiBfAqAtAqCv@iBNo@^}@f@mBVs@`A}Bt@uAfAuCtA}CVe@^e@lByB^Yn@_@NQ^UVOj@QDCVk@d@[d@Mh@CnBa@d@Mx@IbAQRA|Be@\\DJHRVR|@b@N`AJ|Aj@b@TxAjAl@`@`@R`@Z`EfCfAh@j@f@THpA~@zGpFfBlAb@P^Jd@Cx@Wb@i@To@H]LuAA_CFqDRkGJaANw@d@kBjAkD`AgDX{AJmA@_@IeEGqAc@oECs@RaLULXFE^IVONqCa@oAHS\\[V_@RE?UKUSWk@e@sACEOEKDa@Vk@h@YHEMd@u@VmAZq@`Ay@j@_@^]d@Wj@Kd@Of@SZKb@Ul@u@DU?eAFQ@a@M{@@w@CaBHw@BgACI?cCBa@@qCD{@CmADyACaAB[Em@?{@BcDDg@DwDC_B@yACuEJwDD]\\g@`@Gd@?b@DPO@IAUAwCDqCCqB@uBAyADsDA}@DSJIFAr@Jh@@rDC^CBcAAgBCc@EOJiGCwCDqAAcCDi@BeCAo@Kw@ECcBH]DEDENCjBDjEEtC@tHK`B@dFELE@u@C}@Bc@FIJEr@DpB?zBBpE?fKGPEBoBFYPUj@?xSCf@?xACh@C~DAdADbBEhABtA`@l@K\\MpAA~EUt@Ad@D|@GrBNbCMb@MPKH[H{A|@mBz@c@\\]`@s@h@Yj@_@~AIN{@z@Kd@Yd@QfAGvAWj@[`@CJ?FL\\z@xARHt@Jf@Er@QZLb@FxCHXFz@EZ@r@Ar@BTXZlBFfADfE?x@C\\MnAQ|@Qn@y@tBQZ_AjCc@dBIt@"
predicted_score = predict_rarity(polyline)
print(f"Predicted Rarity Score: {predicted_score}")
