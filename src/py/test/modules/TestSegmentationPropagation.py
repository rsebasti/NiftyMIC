## \file TestSegmentationPropagation.py
#  \brief  Class containing unit tests for module SegmentationPropagation
# 
#  \author Michael Ebner (michael.ebner.14@ucl.ac.uk)
#  \date May 2017


## Import libraries 
import SimpleITK as sitk
import numpy as np
import unittest
import sys

## Import modules from src-folder
import base.Stack as st
import utilities.SimpleITKHelper as sitkh

import registration.RegistrationSimpleITK as regsitk
import registration.RegistrationITK as regitk
import registration.NiftyReg as regniftyreg
import registration.SegmentationPropagation as segprop

from definitions import dir_test

## Concept of unit testing for python used in here is based on
#  http://pythontesting.net/framework/unittest/unittest-introduction/
#  Retrieved: Aug 6, 2015
class TestSegmentationPropagation(unittest.TestCase):

    ## Specify input data
    dir_test_data = dir_test

    accuracy = 6

    def setUp(self):
        pass

    def test_registration(self):

        filename = "fetal_brain_0"

        parameters_gd = (0.1, 0.2, -0.3, 0, -4, 10)

        template = st.Stack.from_filename(self.dir_test_data, filename=filename, suffix_mask="_mask", extract_slices=False)

        transform_sitk_gd = sitk.Euler3DTransform()
        transform_sitk_gd.SetParameters(parameters_gd)

        stack_sitk = sitkh.get_transformed_sitk_image(template.sitk, transform_sitk_gd)

        stack = st.Stack.from_sitk_image(stack_sitk, filename="stack")

        # sitkh.show_sitk_image([template.sitk, stack_sitk])

        optimizer = "RegularStepGradientDescent"
        optimizer_params = "{'learningRate': 1, 'minStep': 1e-6, 'numberOfIterations': 300}"

        # optimizer="ConjugateGradientLineSearch"
        # optimizer_params="{'learningRate': 1, 'numberOfIterations': 100}"

        registration = regsitk.RegistrationSimpleITK(initializer_type="MOMENTS", use_verbose=True, metric="MeanSquares", optimizer=optimizer, optimizer_params=optimizer_params)
        # registration = regitk.RegistrationITK()
        # registration = regniftyreg.NiftyReg()

        segmentation_propagation = segprop.SegmentationPropagation(stack=stack, template=template, registration_method=registration, dilation_radius=10)
        segmentation_propagation.run_segmentation_propagation()
        foo = segmentation_propagation.get_segmented_stack()
        # sitkh.show_stacks([template, foo, stack], label=["template", "stack_prop", "stack_orig"])

        transform = segmentation_propagation.get_registration_transform_sitk()
        parameters = sitk.Euler3DTransform(transform.GetInverse()).GetParameters()


        self.assertEqual(np.round(
            np.linalg.norm(np.array(parameters) - parameters_gd)
        , decimals = 0), 0)