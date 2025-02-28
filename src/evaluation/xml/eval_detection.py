from __future__ import division

from collections import defaultdict
import itertools
import numpy as np
import six
from tqdm import tqdm

from src.utils.utils import bbox_iou

def get_box_num(gt_labels, class_num):
    num = [0, ] * class_num
    for label in gt_labels:
        for l in label:
            num[l] += 1

    return num

def get_box_num1(gt_labels, class_num):
    num = [0, ] * class_num
    for label in gt_labels:
            num[label] += 1
    return num

def eval_detection_voc(pred_bboxes, pred_labels, pred_scores, gt_bboxes, gt_labels, class_names,image_id_list,
                       threshold, gt_difficults=None, iou_thresh=0.5, use_07_metric=False):
    """Calculate average precisions based on evaluation code of PASCAL VOC.

    Args:
        pred_bboxes : `y_{min}, x_{min}, y_{max}, x_{max}` of a bounding box.
    """

    # fpr, tpr, thresholds = metrics.roc_curve(gt_labels, pred_labels, y_type == "multiclass", pos_label=16)
    class_count = get_box_num(gt_labels, len(class_names))
    prec, rec, score,tp,fp,fn,error_image = voc_precision_recall(pred_bboxes, pred_labels, pred_scores, gt_bboxes, gt_labels, class_count, class_names,image_id_list, gt_difficults, iou_thresh=iou_thresh)

    ap = voc_ap(prec, rec, use_07_metric=use_07_metric)
    tp1, fp1, precision, recalls, f1, score1 ,f1_,id= voc_F1(tp,fp,prec, rec, score, threshold)

    return {'ap': ap, 'prec':precision, 'rec':recalls, 'num': class_count, 'f1': f1, 'threshold':score1,'tp':tp1,'fp':fp1,'fn':class_count-tp1,'prec_':prec,'rec_':rec,'score_':score,'tp_':tp,'fp_':fp,'fn_':fn,'f1_':f1_,'error':error_image,'id':id}

def voc_precision_recall(pred_bboxes, pred_labels, pred_scores, gt_bboxes, gt_labels, class_count,class_names,image_id_list,
                         gt_difficults=None, iou_thresh=0.5):
    """Calculate precision and recall based on evaluation code of PASCAL VOC.
    """
    pred_bboxes, pred_labels, pred_scores, gt_bboxes, gt_labels,image_id = \
        iter(pred_bboxes), iter(pred_labels), iter(pred_scores), iter(gt_bboxes), iter(gt_labels),iter(image_id_list)

    gt_difficults = itertools.repeat(None) if gt_difficults is None else iter(gt_difficults)
    all_data = six.moves.zip(pred_bboxes, pred_labels, pred_scores, gt_bboxes, gt_labels, gt_difficults,image_id)
    score, match, class_count_l = defaultdict(list), defaultdict(list), defaultdict(list)
    error_image_id=[]
    for pred_bbox, pred_label, pred_score, gt_bbox, gt_label, gt_difficult ,eval_image_id in tqdm(all_data):
        score_iter, match_iter,iou_iter = defaultdict(list), defaultdict(list),defaultdict(list)
        class_count1=get_box_num1(gt_label, len(class_count))
        if gt_difficult is None:
            gt_difficult = np.zeros(gt_bbox.shape[0], dtype=bool)
        iou_one=[]
        for l in np.unique(np.concatenate((pred_label, gt_label)).astype(int)):
            pred_mask_l = pred_label==l
            pred_mask_l=np.array(pred_mask_l).astype("int32").tolist()

            a=[]
            count=-1
            for i in pred_mask_l:
                count+=1
                if i==1:
                    a.append(count)
            pred_bbox_l=[pred_bbox[j] for j in a]
            pred_score_l=[pred_score[m] for m in a]

            #  sort by score
            order = np.array(pred_score_l).argsort()[::-1]
            pred_bbox_l = [pred_bbox_l[n] for n in order]
            pred_bbox_l=np.array(pred_bbox_l)
            pred_score_l = [pred_score_l[n] for n in order]

            gt_mask_l = gt_label == l
            gt_mask_l = np.array(gt_mask_l).astype("int32").tolist()
            a1 = []
            count1 = -1
            for i1 in gt_mask_l:
                count1 += 1
                if i1 == 1:
                    a1.append(count1)

            gt_bbox_l = [gt_bbox[m1] for m1 in a1]
            gt_difficult_l =  [gt_difficult[n1] for n1 in a1]

            score[l].extend(pred_score_l)
            score_iter[l].extend(pred_score_l)

            if len(pred_bbox_l) == 0:
                continue
            if len(gt_bbox_l) == 0:
                match[l].extend((0,) * pred_bbox_l.shape[0])
                match_iter[l].extend((0,) * pred_bbox_l.shape[0])
                continue

            # VOC evaluation follows integer typed bounding boxes.
            pred_bbox_l = pred_bbox_l.copy()
            # pred_bbox_l[:, 2:] += 1
            gt_bbox_l = gt_bbox_l.copy()
            # gt_bbox_l[:, 2:] += 1
            pred_bbox_l=np.array(pred_bbox_l)
            gt_bbox_l=np.array(gt_bbox_l)
            iou = bbox_iou(pred_bbox_l, gt_bbox_l)

            gt_index = iou.argmax(axis=1)

            # set -1 if there is no matching ground truth
            gt_index[iou.max(axis=1) < iou_thresh] = -1
            for io in iou:
                for io1 in io:
                    if io1>iou_thresh:
                        iou_iter[l].extend([io1])
            del iou

            selec = np.zeros(gt_bbox_l.shape[0], dtype=bool)
            for gt_idx in gt_index:
                if gt_idx >= 0:
                    if gt_difficult_l[gt_idx]:
                        match[l].append(-1)
                        match_iter[l].append(-1)

                    else:
                        if not selec[gt_idx]:
                            match[l].append(1)
                            match_iter[l].append(1)
                            class_count_l[l].append(1)
                        else:
                            match[l].append(0)
                            match_iter[l].append(0)
                            class_count_l[l].append(1)
                        selec[gt_idx] = True
                else:
                    match[l].append(0)
                    match_iter[l].append(0)


        n_fg_class = len(class_count)
        prec_iter = [None] * n_fg_class
        rec_iter = [None] * n_fg_class
        tp_iter = [None] * n_fg_class
        fp_iter = [None] * n_fg_class
        score_sort_iter = [None] * n_fg_class
        for l in range(n_fg_class):
            avg_iou=0
            score_l_iter = np.array(score_iter[l])
            match_l_iter = np.array(match_iter[l], dtype=np.int8)

            order_iter = score_l_iter.argsort()[::-1]
            score_sort_iter[l] = score_l_iter[order_iter]
            match_l_iter = match_l_iter[order_iter]

            tp_iter[l] = np.cumsum(match_l_iter == 1)
            fp_iter[l] = np.cumsum(match_l_iter == 0)

            # If an element of fp + tp is 0,
            # the corresponding element of prec[l] is nan.
            prec_iter[l] = tp_iter[l] / (fp_iter[l] + tp_iter[l])
            # If n_pos[l] is 0, rec[l] is None.
            if class_count1[l] > 0:
                rec_iter[l] = tp_iter[l] / class_count1[l]

            if iou_iter[l] !=[]:
                b=0
                for i in iou_iter[l]:
                    b+=i
                avg_iou=b/len(iou_iter[l])

            tp,fp,precision, recalls, f1, score1,_,_1 = voc_F1(tp_iter,fp_iter,prec_iter, rec_iter, score_sort_iter, None)


            print("class_id = %d, name = %s, count = %s, (TP = %d, FP = %d，FN = %d, precision = %.2f%%, recalls = %.2f%%, f1 = %.2"
                  "f%%, avg_iou = %f) "% (l,class_names[l],str(len(class_count_l[l]))+"/"+str(class_count[l]),np.nan_to_num(tp[l]),np.nan_to_num(fp[l]),class_count1[l]-np.nan_to_num(tp[l]),precision[l],recalls[l],f1[l],isnan(avg_iou)))

            if np.nan_to_num(fp[l]) > 0 or class_count1[l]-np.nan_to_num(tp[l]) > 0:
                error_image_id.append(eval_image_id +"---"+class_names[l]+ "+FP:" + str(np.nan_to_num(fp[l])) + "+FN:" + str(class_count1[l]-np.nan_to_num(tp[l])))
            if isnan(avg_iou) !=0:
                 iou_one.append(avg_iou)

        tp_one,fp_one,pre_one, rec_one, f1_one, score_one,_ ,_1= voc_F1(tp_iter,fp_iter,prec_iter, rec_iter, score_sort_iter, None)
        # tp_one,fp_one,pre_one,rec_one,f1_one,score_one=np.nansum(tp_one),np.nansum(fp_one),np.nanmean(pre_one),np.nanmean(rec_one),np.nanmean(f1_one),np.nanmean(score_one)
        tp_one,fp_one,score_one=np.nansum(tp_one),np.nansum(fp_one),np.nanmean(score_one)
        FN_one=np.sum(class_count1)-tp_one
        pre_one, rec_one, f1_one=get_metric(int(tp_one),int(fp_one),int(FN_one))
        print(
            "\n (for conf_fresh =%.3f, TP = %d, FP = %d，FN = %d, precision = %.2f%%, recalls = %.2f%%, f1 = %.2f%%, avg_iou = %f) " % (
            score_one,int(tp_one),int(fp_one),int(FN_one),pre_one,rec_one,f1_one,np.sum(iou_one)/len(iou_one)))
        print("-------------------------------------------------------------------------------------------------------------------------")

    for iter_ in (
            pred_bboxes, pred_labels, pred_scores,
            gt_bboxes, gt_labels, gt_difficults):
        if next(iter_, None) is not None:
            raise ValueError('Length of input iterables need to be same.')

    n_fg_class = len(class_count)
    prec = [None] * n_fg_class
    rec = [None] * n_fg_class
    tp_cl= [None] * n_fg_class
    fp_cl= [None] * n_fg_class
    fn_cl= [None] * n_fg_class
    score_sort = [None] * n_fg_class

    for l in range(n_fg_class):
        score_l = np.array(score[l])
        match_l = np.array(match[l], dtype=np.int8)

        order = score_l.argsort()[::-1]
        score_sort[l] = score_l[order]
        match_l = match_l[order]

        tp_cl[l] = np.cumsum(match_l == 1)
        fp_cl[l] = np.cumsum(match_l == 0)

        # If an element of fp + tp is 0,
        # the corresponding element of prec[l] is nan.
        prec[l] = tp_cl[l] / (fp_cl[l] + tp_cl[l])
        # If n_pos[l] is 0, rec[l] is None.
        if class_count[l] > 0:
            rec[l] = tp_cl[l] / class_count[l]
            fn_cl[l]=class_count[l]-tp_cl[l]
        else:
            fn_cl[l]=np.nan
    return prec, rec, score_sort,tp_cl,fp_cl,fn_cl,error_image_id

def isnan(p):
    if p is None:
        return 0
    else:
        return p

def voc_ap(prec, rec, use_07_metric=False):
    """Calculate average precisions based on evaluation code of PASCAL VOC.
    """
    n_fg_class = len(prec)
    ap = defaultdict(list)
    for l in six.moves.range(n_fg_class):
        if prec[l] is None or rec[l] is None:
            ap[l] = np.nan
            continue
        for i in range(len(prec[l])):
            prec1=prec[l][:len(prec[l])-i]
            rec1=rec[l][:len(prec[l])-i]

            if use_07_metric:
                # 11 point metric
                ap[l] = 0
                for t in np.arange(0., 1.1, 0.1):
                    if np.sum(rec[l] >= t) == 0:
                        p = 0
                    else:
                        p = np.max(np.nan_to_num(prec[l])[rec[l] >= t])
                    ap[l] += p / 11
            else:
                # correct AP calculation
                # first append sentinel values at the end
                mpre = np.concatenate(([0], np.nan_to_num(prec1), [0]))
                mrec = np.concatenate(([0], rec1, [1]))

                mpre = np.maximum.accumulate(mpre[::-1])[::-1]

                # to calculate area under PR curve, look for points
                # where X axis (recall) changes value
                i = np.where(mrec[1:] != mrec[:-1])[0]

                # and sum (\Delta recall) * prec
                ap[l].append(np.sum((mrec[i + 1] - mrec[i]) * mpre[i + 1]))
        ap[l] = ap[l][::-1]

    ap_f=[None]*n_fg_class
    for m in range(n_fg_class):
        ap_f[m]=ap[m]
    return ap_f

def voc_F1(tp_,fp_,prec, rec, score, threshold):
    """Calculate average precisions based on evaluation code of PASCAL VOC.
    """
    n_fg_class = len(prec)
    f1 = np.empty(n_fg_class)
    F1_=[None]*n_fg_class
    id_=[None]*n_fg_class
    tp,fp,score_threshold, precision, recall =f1.copy(), f1.copy(), f1.copy(), f1.copy(), f1.copy()

    for l in six.moves.range(n_fg_class):
        if prec[l] is None or rec[l] is None:
            id_[l],F1_[l],tp[l],fp[l],f1[l], precision[l], recall[l], score_threshold[l] = np.nan,np.nan,np.nan, np.nan,np.nan, np.nan, np.nan, np.nan
            continue

        # first append sentinel values at the end
        mtp = np.concatenate(([0], np.nan_to_num(tp_[l]), [0]))
        mfp = np.concatenate(([0], np.nan_to_num(fp_[l]), [0]))
        mpre = np.concatenate(([0], np.nan_to_num(prec[l]), [0]))
        mscore = np.concatenate(([0], np.nan_to_num(score[l]), [0]))
        mrec = np.concatenate(([0], rec[l], [1]))

        mpre = np.maximum.accumulate(mpre[::-1])[::-1]
        F1_l = 2 / (1/mrec + 1/mpre)
        F1_[l]=F1_l.tolist()

        id_max_prec = min(len(mpre) - np.nanargmax(mpre[::-1]), len(mpre) - 1)
        id_max_recall = max(0, np.nanargmax(mrec) - 2)
        id_score = np.sum(mscore > 0.5)
        id_max_f1 = np.nanargmax(F1_l)

        id = id_max_f1 if threshold is None else np.sum(mscore > threshold[l])
        tp[l],fp[l],f1[l], precision[l], recall[l], score_threshold[l] = mtp[id],mfp[id],F1_l[id], mpre[id], mrec[id], mscore[id]
        id_[l]=id-1
    return tp,fp,precision, recall, f1, score_threshold,F1_,id_

def get_metric(tp,fp,fn):
    if tp+fp==0 or tp+fn==0:
        return 0,0,0

    prec=tp/(tp+fp)
    rec=tp/(tp+fn)
    f1=2/(1/prec+1/rec)
    return prec,rec,f1
