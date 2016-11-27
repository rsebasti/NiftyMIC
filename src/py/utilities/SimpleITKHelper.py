## \file SimpleITKHelper.py
#  \brief  
# 
#  \author Michael Ebner (michael.ebner.14@ucl.ac.uk)
#  \date September 2015


## Import libraries
import os                       # used to execute terminal commands in python
import SimpleITK as sitk
import itk
import numpy as np
import nibabel as nib
import matplotlib.pyplot as plt
import datetime
import fnmatch
import re

## Import modules
import utilities.PythonHelper as ph

## Import modules from src-folder
# import utilities.SimpleITKHelper as sitkh

## Use ITK-SNAP instead of imageJ to view images
# os.environ['SITK_SHOW_COMMAND'] = "/Applications/ITK-SNAP.app/Contents/MacOS/ITK-SNAP"
os.environ['SITK_SHOW_COMMAND'] = "/usr/local/bin/itksnap"
# os.environ['SITK_SHOW_COMMAND'] = "itksnap"

# np.set_printoptions(precision=3)

## AddTransform does not work! Python always crashes! Moreover, the composition
# of AddTransform is stack based, i.e. first in -- last applied. Wtf!?
# \param[in] sitk::simple::AffineTransform or EulerxDTransform for inner and outer transform
# \see http://insightsoftwareconsortium.github.io/SimpleITK-Notebooks/22_Transforms.html
def get_composite_sitk_affine_transform(transform_outer, transform_inner):
    
    ## Guarantee type sitk::simple::AffineTransform of transformations
    # transform_outer = sitk.AffineTransform(transform_outer)
    # transform_inner = sitk.AffineTransform(transform_inner)

    dim = transform_outer.GetDimension()

    A_inner = np.asarray(transform_inner.GetMatrix()).reshape(dim,dim)
    c_inner = np.asarray(transform_inner.GetCenter())
    t_inner = np.asarray(transform_inner.GetTranslation())

    A_outer = np.asarray(transform_outer.GetMatrix()).reshape(dim,dim)
    c_outer = np.asarray(transform_outer.GetCenter())
    t_outer = np.asarray(transform_outer.GetTranslation())

    A_composite = A_outer.dot(A_inner)
    c_composite = c_inner
    t_composite = A_outer.dot(t_inner + c_inner - c_outer) + t_outer + c_outer - c_inner

    ## appropriate_transform needs to be the "biggest" of inner and outer trafo
    # composite_transform = sitk.Transform(appropriate_transform)
    # composite_transform.SetMatrix(A_composite)
    # composite_transform.SetCenter(c_composite)
    # composite_transform.SetTranslation(t_composite)
    # return composite_transform

    return sitk.AffineTransform(A_composite.flatten(), t_composite, c_composite)


## Composite two Euler Transforms
# \param[in] transform_outer as sitk::simple::EulerxDTransform
# \param[in] transform_inner as sitk::simple::EulerxDTransform
# \return \p tranform_outer \f$ \circ \f$ \p transform_inner as sitk.EulerxDTransform
# \see http://insightsoftwareconsortium.github.io/SimpleITK-Notebooks/22_Transforms.html
def get_composite_sitk_euler_transform(transform_outer, transform_inner):
    
    ## Guarantee type sitk::simple::AffineTransform of transformations
    # transform_outer = sitk.AffineTransform(transform_outer)
    # transform_inner = sitk.AffineTransform(transform_inner)

    dim = transform_outer.GetDimension()

    A_inner = np.asarray(transform_inner.GetMatrix()).reshape(dim,dim)
    c_inner = np.asarray(transform_inner.GetCenter())
    t_inner = np.asarray(transform_inner.GetTranslation())

    A_outer = np.asarray(transform_outer.GetMatrix()).reshape(dim,dim)
    c_outer = np.asarray(transform_outer.GetCenter())
    t_outer = np.asarray(transform_outer.GetTranslation())

    A_composite = A_outer.dot(A_inner)
    c_composite = c_inner
    t_composite = A_outer.dot(t_inner + c_inner - c_outer) + t_outer + c_outer - c_inner

    euler = eval("sitk." + transform_outer.GetName() + "()")
    euler.SetMatrix(A_composite.flatten())
    euler.SetTranslation(t_composite)
    euler.SetCenter(c_composite)

    return euler


## Get direction for sitk.Image object from sitk.AffineTransform instance.
#  The information of the image is required to extract spacing information and 
#  associated image dimension
#  \param[in] affine_transform_sitk sitk.AffineTransform instance
#  \param[in] image_or_spacing_sitk provide entire image as sitk object or spacing directly
#  \return image direction which can be used to update the sitk.Image via
#          image_sitk.SetDirection(direction)
def get_sitk_image_direction_from_sitk_affine_transform(affine_transform_sitk, image_or_spacing_sitk):
    dim = affine_transform_sitk.GetDimension()
    try:
        spacing_sitk = np.array(image_or_spacing_sitk.GetSpacing())
    except:
        spacing_sitk = np.array(image_or_spacing_sitk)

    S_inv_sitk = np.diag(1/spacing_sitk)

    A = np.array(affine_transform_sitk.GetMatrix()).reshape(dim,dim)

    return A.dot(S_inv_sitk).flatten()


## Get origin for sitk.Image object from sitk.AffineTransform instance.
#  The information of the image is required to extract spacing information and 
#  associated image dimension
#  \param[in] affine_transform_sitk sitk.AffineTransform instance
#  \param[in] image_sitk image as sitk.Image object sought to be updated
#  \return image origin which can be used to update the sitk.Image via
#          image_sitk.SetOrigin(origin)
#  TODO: eliminate image_sitk from the header
def get_sitk_image_origin_from_sitk_affine_transform(affine_transform_sitk, image_sitk=None):
    """
    Important: Only tested for center=\0! Not clear how it shall be implemented,
            cf. Johnson2015a on page 551 vs page 107!

    Mostly outcome of application of get_composite_sitk_affine_transform and first transform_inner is image. 
    Therefore, center_composite is always zero on tested functions so far
    """
    # dim = len(image_sitk.GetSize())
    dim = affine_transform_sitk.GetDimension()

    affine_center = np.array(affine_transform_sitk.GetCenter())
    affine_translation = np.array(affine_transform_sitk.GetTranslation())
    
    R = np.array(affine_transform_sitk.GetMatrix()).reshape(dim,dim)

    return affine_center + affine_translation 
    # return affine_center + affine_translation - R.dot(affine_center)


## Gets the sitk affine transform from sitk image, to transform an index to the
# physical space
# \date       2016-11-06 18:54:09+0000
#
# Returns the affine transform of an sitk image which links the voxel space
# (i.e. its data array elements) with the p positions in the physical space.
# I.e. it transforms a voxel index to the physical coordinate:
# \f[ T(\vec{i}) = R\,S\,\vec(i) + \vec{o} = \vec{x}
# \f] with
# \f$R\f$ being the rotation matrix (direction matrix via \p GetDirection),
# \f$S=diag(s_i)\f$ the scaling matrix,
# \f$\vec{i}\f$ the voxel index,
# \f$\vec{o}\f$ the image origin (via \p GetOrigin) and
# \f$\vec{x}\f$ the final physical coordinate.
#
# \param      image_sitk  The image sitk
#
# \return     Transform T(i) = R*S*i + origin as sitk.AffineTransform
#
def get_sitk_affine_transform_from_sitk_image(image_sitk):
    
    ## Matrix A = R*S
    A = get_sitk_affine_matrix_from_sitk_image(image_sitk)

    ## Translation t = origin
    t = np.array(image_sitk.GetOrigin())

    ## T(i) = R*S*i + origin
    return sitk.AffineTransform(A,t)


##
# Gets the sitk affine matrix from sitk image.
# \date       2016-11-06 19:07:03+0000
#
#
# \param      image_sitk  The image sitk
#
# \return     Matrix R*S as flattened data array ready for SetMatrix
#
def get_sitk_affine_matrix_from_sitk_image(image_sitk):
    dim = len(image_sitk.GetSize())
    spacing_sitk = np.array(image_sitk.GetSpacing())
    S_sitk = np.diag(spacing_sitk)
    R_sitk = np.array(image_sitk.GetDirection()).reshape(dim,dim)

    return R_sitk.dot(S_sitk).flatten()


## Get sitk.AffineTransform object based on direction and origin. The idea is,
#  to get the affine transform which describes the physical position of the
#  respective image.
#  The information of the image is required to extract spacing information and 
#  associated image dimension
#  \param[in] direction_sitk direction obtained via GetDirection() of sitk.Image or similar
#  \param[in] origin_sitk origin obtained via GetOrigin() of sitk.Image or similar
#  \param[in] image_or_spacing_sitk provide entire image as sitk object or spacing directly
#  \return Affine transform as sitk.AffineTransform object
def get_sitk_affine_transform_from_sitk_direction_and_origin(direction_sitk, origin_sitk, image_or_spacing_sitk):
    dim = len(origin_sitk)
    try:
        spacing_sitk = np.array(image_or_spacing_sitk.GetSpacing())
    except:
        spacing_sitk = np.array(image_or_spacing_sitk)

    S_sitk = np.diag(spacing_sitk)

    direction_matrix_sitk = np.array(direction_sitk).reshape(dim,dim)
    affine_matrix_sitk = direction_matrix_sitk.dot(S_sitk).flatten()

    return sitk.AffineTransform(affine_matrix_sitk, origin_sitk)


## rigid_transform_*D (object type  Transform) as output of object sitk.ImageRegistrationMethod does not contain the
## member functions GetCenter, GetTranslation, GetMatrix whereas the objects sitk.Euler*DTransform does.
## Hence, create an instance sitk.Euler*D so that it can be used for composition of transforms as coded 
## in get_composite_sitk_affine_transform
def get_inverse_of_sitk_rigid_registration_transform(rigid_registration_transform):

    dim = rigid_registration_transform.GetDimension()

    if dim == 2:
        rigid_transform_2D = rigid_registration_transform

        ## Steps could have been chosen the same way as in the 3D case. However,
        ## here the computational steps more visible

        ## Extract parameters of 2D registration
        angle, translation_x, translation_y = rigid_transform_2D.GetParameters()
        center = rigid_transform_2D.GetFixedParameters()

        ## Create transformation used to align moving -> fixed

        ## Obtain inverse translation
        tmp_trafo = sitk.Euler2DTransform((0,0),-angle,(0,0))
        translation_inv = tmp_trafo.TransformPoint((-translation_x, -translation_y))

        ## Create instance of Euler2DTransform based on inverse = R_inv(x-c) - R_inv(t) + c
        return sitk.Euler2DTransform(center, -angle, translation_inv)

    elif dim == 3:
        rigid_transform_3D = rigid_registration_transform

        ## Create inverse transform of type Transform
        rigid_transform_3D_inv = rigid_transform_3D.GetInverse()

        ## Extract parameters of inverse 3D transform to feed them back to object Euler3DTransform:
        angle_x, angle_y, angle_z, translation_x, translation_y, translation_z = rigid_transform_3D_inv.GetParameters()
        center = rigid_transform_3D_inv.GetFixedParameters()

        ## Return inverse of rigid_transform_3D as instance of Euler3DTransform
        return sitk.Euler3DTransform(center, angle_x, angle_y, angle_z, (translation_x, translation_y, translation_z))
 

## Get transformed (deepcopied) image
#  \param[in] image_init_sitk image as sitk.Image object to be transformed
#  \param[in] transform_sitk transform to be applied as sitk.AffineTransform object
#  \return transformed image as sitk.Image object
def get_transformed_sitk_image(image_init_sitk, transform_sitk):
    image_sitk = sitk.Image(image_init_sitk)
    
    affine_transform_sitk = get_sitk_affine_transform_from_sitk_image(image_sitk)

    transform_sitk = get_composite_sitk_affine_transform(transform_sitk, affine_transform_sitk)
    # transform_sitk = get_composite_sitk_affine_transform(get_inverse_of_sitk_rigid_registration_transform(affine_transform_sitk), affine_transform_sitk)

    direction = get_sitk_image_direction_from_sitk_affine_transform(transform_sitk, image_sitk)
    origin = get_sitk_image_origin_from_sitk_affine_transform(transform_sitk, image_sitk)

    image_sitk.SetOrigin(origin)
    image_sitk.SetDirection(direction)

    return image_sitk


## Read image from file and return as ITK obejct
#  \param[in] filename filename of image to read
#  \param[in] pixel_type itk pixel types, like itk.D, itk.F, itk.UC etc
#  \example read_itk_image("image.nii.gz", itk.D, 3) to read image stack
#  \example read_itk_image("mask.nii.gz", itk.UC, 3) to read image stack mask
def read_itk_image(filename, pixel_type=itk.D, dim=3):
    image_type = itk.Image[pixel_type, dim]
    # image_IO_type = itk.NiftiImageIO

    reader = itk.ImageFileReader[image_type].New()
    reader.SetFileName(filename)
    # reader.SetImageIO(image_IO)

    reader.Update()
    image_itk = reader.GetOutput()
    image_itk.DisconnectPipeline()

    return image_itk


##
#       Reads 3D vector image and return as SimpleITK image
# \date       2016-09-20 15:31:05+0100
#
# \param      filename             The filename
# \param      return_vector_index  Index/Component of vector image to be
#                                  returned. If 'None' the entire vector image
#                                  is returned
#
# \return     (Multi-component) sitk.Image object
#
def read_sitk_vector_image(filename, return_vector_index=None):

    ## Workaround: Read vector image via nibabel
    image_nib = nib.load(filename)
    nda_nib = image_nib.get_data()
    nda_nib_shape = nda_nib.shape
    nda = np.zeros((nda_nib_shape[2], nda_nib_shape[1], nda_nib_shape[0], nda_nib_shape[3]))

    ## Convert to (Simple)ITK data array format, i.e. reorder to z-y-x shape
    for i in range(0, nda_nib_shape[2]):
        for k in range(0, nda_nib_shape[0]):
            nda[i,:,k,:] = nda_nib[k,:,i,:]          

    ## Get SimpleITK image
    image_sitk = sitk.GetImageFromArray(nda)

    ## Workaround: Update header from nibabel information
    R = np.array([
        [-1, 0, 0],
        [0, -1, 0],
        [0, 0, 1]])
    affine_nib = image_nib.affine
    R_nib = affine_nib[0:-1,0:-1]

    ## Get spacing (only for image dimensions, i.e. not for the vector component)
    spacing_sitk = np.array(image_nib.header.get_zooms())[0:R_nib.shape[0]]
    S_nib_inv = np.diag(1/spacing_sitk)
    
    direction_sitk = R.dot(R_nib).dot(S_nib_inv).flatten()

    t_nib = affine_nib[0:-1,3]
    origin_sitk = R.dot(t_nib)

    image_sitk.SetSpacing(np.array(spacing_sitk).astype('double'))
    image_sitk.SetDirection(direction_sitk)
    image_sitk.SetOrigin(origin_sitk)

    if return_vector_index is None:
        return image_sitk
    else:
        return sitk.VectorIndexSelectionCast(image_sitk, return_vector_index)

    ## All the other stuff did not work (neither in ITK nor in SimpleITK)! See
    ## below. Readings worked but the two components always contained the same
    ## value!
    # IMAGE_TYPE = itk.Image.D3
    # # IMAGE_TYPE = itk.Image.VD23
    # # IMAGE_TYPE = itk.VectorImage.D3
    # # IMAGE_TYPE = itk.Image.VF23
    # reader = itk.ImageFileReader[IMAGE_TYPE].New()
    # reader.SetFileName(DIR_INPUT + filename_ref + ".nii")
    # reader.Update()
    # foo_itk = reader.GetOutput()


## Write itk image to hard disk as nii.gz image type
#  \param[in] image_itk image to be written as itk.Image object
#  \param[in] filename filename including file ending ".nii.gz"
def write_itk_image(image_itk, filename):

    ## Get image type and dimension for setting up the writer
    dim = image_itk.GetImageDimension()
    type_image_itk = type(image_itk)

    if type_image_itk is itk.Image[itk.D, dim]:
        image_type = itk.Image[itk.D, dim]

    elif type_image_itk is itk.Image[itk.UC, dim]:
        image_type = itk.Image[itk.UC, dim]

    else:
        raise ValueError("Error: ITK image type not known to set up image writer")

    ## Define writer
    writer = itk.ImageFileWriter[image_type].New()
    # image_IO_type = itk.NiftiImageIO

    ## Write image_itk
    writer.SetInput(image_itk)
    writer.SetFileName(filename)
    writer.Update()


##
#       Print the ITK direction matrix
# \date       2016-09-20 15:52:28+0100
#
# \param      direction_itk  direction as obtained via image_itk.GetDirection()
#
def print_itk_direction(direction_itk):
    m_vnl = direction_itk.GetVnlMatrix()
    n_cols = m_vnl.cols()
    n_rows = m_vnl.rows()

    m_np = np.zeros((n_cols, n_rows))

    for i in range(0, n_cols):
        for j in range(0, n_rows):
            m_np[i,j] = m_vnl(i,j)

    print m_np


##
#       Print the ITK array
# \date       2016-11-17 19:51:53+0000
#
# The itk-array can be instantiated via \p array_itk = \p itk.Array2D[itk.D]().
# Depending on the further use the size needs to be defined too, i.e. \p
# array_itk.SetSize(m,n)
#
# \param      array_itk  array as itk.Array2D# \f$ \in R^{m \times n} \f$
#                        or parameter type of itk transforms
#
def print_itk_array(array_itk):
    
    ## itk.Array2D[itk.D]()
    try:
        nda = get_numpy_from_itk_array(array_itk)
    
    ## Parameter type
    except:
        N = array_itk.size()
        nda = np.zeros(N)

        ## Fill array information
        for i in range(0, N):
            nda[i] = array_itk.GetElement(i)

    ## Print array
    print nda
        

def update_itk_parameters(parameters_itk, array):
    for i in range(0, array.size):
        parameters_itk.SetElement(i, array[i])

##
#       Gets the numpy from itk array.
# \date       2016-11-18 11:59:18+0000
#
# \todo That is VERY slow! needs improvement but no clue how to access the
# array quicker
#
# \param      array_itk  The array itk
#
# \return     The numpy from itk array.
#
def get_numpy_from_itk_array(array_itk):
    cols = array_itk.cols()
    rows = array_itk.rows()
    nda = np.zeros((rows, cols))
    
    ## Fill array information
    for i in range(0, rows):
        for j in range(0, cols):
            nda[i,j] = array_itk(i,j)

    return nda


##
# Gets the indices array to flattened sitk image data array.
# \date       2016-11-21 00:26:27+0000
#
# Get an (image_dimension x N_voxels)-numpy array which holds the indices 
# corresponding to a sitk.GetArrayFromImage(image_sitk).flatten() data array
# 
# \param      image_sitk  The image sitk
#
# \return     (image_dimension x N_voxels)-numpy array 
#
def get_indices_array_to_flattened_sitk_image_data_array(image_sitk):

    shape = np.array(image_sitk.GetSize())[::-1]
    dim = image_sitk.GetDimension()

    x = np.arange(0,shape[0])
    y = np.arange(0,shape[1])
    if dim is 3:
        z = np.arange(0,shape[2])
    
    if dim is 2:
        X,Y = np.meshgrid(x,y, indexing='ij') # 'ij' yields vertical x-coordinate for image!
        
        ## Index array (2xN_voxels) of image in voxel space
        indices = np.array([Y.flatten(), X.flatten()])
    else:
        X,Y,Z = np.meshgrid(x,y,z, indexing='ij') # 'ij' yields vertical x-coordinate for image!
        
        ## Index array (3xN_voxels) of image in voxel space
        indices = np.array([Z.flatten(), Y.flatten(), X.flatten()])

    return indices

##
# Gets the numpy array of jacobian itk transform applied on stack.
# \date          2016-11-18 12:00:05+0000
#
# Compute
# \f$ \frac{d\vec{T}}{d\vec{\theta}}(\vec{x}, \vec{\theta})
# \f$ for all points of the stack. The used parameter values
# \f$ \theta
# \f$ for evaluation are encoded in \p transform_itk.
#
# \param[in]     transform_itk                    Transform as itk object
# \param[in]     stack                            Image as Stack object
# \param[in]     points                           Grid points of image as
#                                                 (Dimension x N_voxel)-array.
# \param[in,out] jacobian_transform_on_image_nda  (N_voxel x transform_DOF)-
#                                                 array.
#
# \return        The (N_voxel x transform_DOF)-numpy array of the Jacobian of
#                the transform applied on the stack
#
def get_numpy_array_of_jacobian_itk_transform_applied_on_sitk_image(transform_itk, image_sitk, points=None, jacobian_transform_on_image_nda=None):

    ## Shape of corresponding image data array
    shape = np.array(image_sitk.GetSize())
    dim = image_sitk.GetDimension()

    ## Shall reduce the computational burden in case points stay the same.
    ## However, it does not add much to the computational time
    if points is None:

        ## Index array (dimension x N_voxels) of image in voxel space
        indices = get_indices_array_to_flattened_sitk_image_data_array(image_sitk)
        
        ## Get transform from voxel to image space coordinates
        A = get_sitk_affine_matrix_from_sitk_image(image_sitk).reshape(dim,dim)
        t = np.array(image_sitk.GetOrigin()).reshape(dim,1)
        
        ## Compute point array (3xN_voxels) of image in image space
        points = A.dot(indices) + t

    if jacobian_transform_on_image_nda is None:
        ## Allocate memory
        transform_dof = int(transform_itk.GetNumberOfParameters())
        jacobian_transform_on_image_nda = np.zeros((points.shape[1], dim, transform_dof))

    ## Create 2D itk-array
    jacobian_transform_on_point_itk = itk.Array2D[itk.D]()
    
    ## Evaluate the Jacobian of transform at all points
    for i in range(0, points.shape[1]):
        
        ## Compute Jacobian of transform w.r.t. parameters evaluated at point
        ## jacobian_transform_point_itk is (Dimension x transform_DOF) array
        transform_itk.ComputeJacobianWithRespectToParameters(points[:,i], jacobian_transform_on_point_itk)

        ## Convert itk to numpy array
        ## THE computational time consuming part!
        jacobian_transform_on_image_nda[i,:,:] = get_numpy_from_itk_array(jacobian_transform_on_point_itk)

    ## Return Jacobian w.r.t to parameters evaluated at all image points
    return jacobian_transform_on_image_nda


## Extract direction from SimpleITK-image so that it can be injected into
#  ITK-image
#  \param[in] image_sitk sitk.Image object
#  \return direction as itkMatrix object
def get_itk_direction_from_sitk_image(image_sitk):
    direction_sitk = image_sitk.GetDirection()

    return get_itk_from_sitk_direction(direction_sitk)


## Extract direction from ITK-image so that it can be injected into
#  SimpleITK-image
#  \param[in] image_itk itk.Image object
#  \return direction as 1D array of size dimension^2, np.array
def get_sitk_direction_from_itk_image(image_itk):
    direction_itk = image_itk.GetDirection()

    return get_sitk_from_itk_direction(direction_itk)


## Convert direction from sitk.Image to itk.Image direction format
#  \param[in] direction_sitk direction obtained via GetDirection() of sitk.Image
#  \return direction which can be set as SetDirection() at itk.Image
def get_itk_from_sitk_direction(direction_sitk):
    dim = np.sqrt(len(direction_sitk)).astype('int')
    m = itk.vnl_matrix_fixed[itk.D, dim, dim]()

    for i in range(0, dim):
        for j in range(0, dim):
            m.set(i,j,direction_sitk[dim*i + j])

    return itk.Matrix[itk.D, dim, dim](m)    
    

## Convert direction from itk.Image to sitk.Image direction format
#  \param[in] direction_itk direction obtained via GetDirection() of itk.Image
#  \return direction which can be set as SetDirection() at sitk.Image
def get_sitk_from_itk_direction(direction_itk):
    vnl_matrix = direction_itk.GetVnlMatrix()
    dim = np.sqrt(vnl_matrix.size()).astype('int')

    direction_sitk = np.zeros(dim*dim)
    for i in range(0, dim):
        for j in range(0, dim):
            direction_sitk[i*dim + j] = vnl_matrix(i,j)

    return direction_sitk


## Convert itk.Euler3DTransform to sitk.Euler3DTransform instance
#  \param[in] Euler3DTransform_itk itk.Euler3DTransform instance
#  \return converted sitk.Euler3DTransform instance
def get_sitk_from_itk_Euler3DTransform(Euler3DTransform_itk):
    parameters_itk = Euler3DTransform_itk.GetParameters()
    fixed_parameters_itk = Euler3DTransform_itk.GetFixedParameters()
    
    N_params = parameters_itk.GetNumberOfElements()
    N_fixedparams = fixed_parameters_itk.GetNumberOfElements()
    
    parameters_sitk = np.zeros(N_params)
    fixed_parameters_sitk = np.zeros(N_fixedparams)

    for i in range(0, N_params):
        parameters_sitk[i] = parameters_itk.GetElement(i)

    for i in range(0, N_fixedparams):
        fixed_parameters_sitk[i] = fixed_parameters_itk.GetElement(i)


    Euler3DTransform_sitk = sitk.Euler3DTransform()
    Euler3DTransform_sitk.SetParameters(parameters_sitk)
    Euler3DTransform_sitk.SetFixedParameters(fixed_parameters_sitk)

    return Euler3DTransform_sitk


## Convert itk.AffineTransform to sitk.AffineTransform instance
#  \param[in] AffineTransform_itk itk.AffineTransform instance
#  \return converted sitk.AffineTransform instance
def get_sitk_from_itk_AffineTransform(AffineTransform_itk):

    dim = len(AffineTransform_itk.GetTranslation())

    parameters_itk = AffineTransform_itk.GetParameters()
    fixed_parameters_itk = AffineTransform_itk.GetFixedParameters()
    
    N_params = parameters_itk.GetNumberOfElements()
    N_fixedparams = fixed_parameters_itk.GetNumberOfElements()
    
    parameters_sitk = np.zeros(N_params)
    fixed_parameters_sitk = np.zeros(N_fixedparams)

    for i in range(0, N_params):
        parameters_sitk[i] = parameters_itk.GetElement(i)

    for i in range(0, N_fixedparams):
        fixed_parameters_sitk[i] = fixed_parameters_itk.GetElement(i)


    AffineTransform_sitk = sitk.AffineTransform(dim)
    AffineTransform_sitk.SetParameters(parameters_sitk)
    AffineTransform_sitk.SetFixedParameters(fixed_parameters_sitk)

    return AffineTransform_sitk


## Convert SimpleITK-image to ITK-image
#  \todo Check whether it is sufficient to just set origin, spacing and direction!
#  \param[in] image_sitk SimpleITK-image to be converted, sitk.Image object
#  \return converted image as itk.Image object
def get_itk_from_sitk_image(image_sitk):

    ## Extract information ready to use for ITK-image
    dimension = image_sitk.GetDimension()
    origin = image_sitk.GetOrigin()
    spacing = image_sitk.GetSpacing()
    direction = get_itk_direction_from_sitk_image(image_sitk)
    nda = sitk.GetArrayFromImage(image_sitk)

    ## Define ITK image type according to pixel type of sitk.Object
    if image_sitk.GetPixelIDValue() is sitk.sitkFloat64:
        ## image stack
        image_type = itk.Image[itk.D, dimension]
    else:
        ## mask stack
        ## Couldn't use itk.UC (which apparently is used for masks normally)
        ## or any other "smaller format than itk.D" since 
        ## itk.MultiplyImageFilter[itk.UC, itk.D] does not work! (But
        ## which I need within InverseProblemSolver)
        image_type = itk.Image[itk.D, dimension]
        # image_type = itk.Image[itk.UI, dimension]
        # image_type = itk.Image[itk.UC, dimension]

    ## Create ITK image
    itk2np = itk.PyBuffer[image_type]
    image_itk = itk2np.GetImageFromArray(nda) 

    image_itk.SetOrigin(origin)
    image_itk.SetSpacing(spacing)
    image_itk.SetDirection(direction)

    image_itk.DisconnectPipeline()

    return image_itk


## Convert ITK-image to SimpleITK-image
#  \todo Check whether it is sufficient to just set origin, spacing and direction!
#  \param[in] image_itk ITK-image to be converted, itk.Image object
#  \return converted image as sitk.Image object
def get_sitk_from_itk_image(image_itk):

    ## Extract information ready to use for SimpleITK-image
    dimension = image_itk.GetLargestPossibleRegion().GetImageDimension()
    origin = np.array(image_itk.GetOrigin())
    spacing = np.array(image_itk.GetSpacing())
    direction = get_sitk_direction_from_itk_image(image_itk)

    image_type = itk.Image[itk.D, dimension]
    itk2np = itk.PyBuffer[image_type]
    nda = itk2np.GetArrayFromImage(image_itk)

    ## Create SimpleITK-image
    image_sitk = sitk.GetImageFromArray(nda)

    image_sitk.SetOrigin(origin)
    image_sitk.SetSpacing(spacing)
    image_sitk.SetDirection(direction)

    return image_sitk

##
#       Print
# \date       2016-11-06 15:43:19+0000
#
# \param      rigid_affine_similarity_transform_sitk  The rigid affine similarity transform sitk
# \param      text                                    The text
#
# \return     { description_of_the_return_value }
#
def print_sitk_transform(rigid_affine_similarity_transform_sitk, text=None):

    dim = rigid_affine_similarity_transform_sitk.GetDimension()

    if text is None:
        text = rigid_affine_similarity_transform_sitk.GetName()
    
    matrix = np.array(rigid_affine_similarity_transform_sitk.GetMatrix()).reshape(dim,dim)
    translation = np.array(rigid_affine_similarity_transform_sitk.GetTranslation())
    
    parameters = np.array(rigid_affine_similarity_transform_sitk.GetParameters())
    center = np.array(rigid_affine_similarity_transform_sitk.GetFixedParameters())

    print("\t\t" + text + ":")
    print("\t\t\tcenter = " + str(center))
    
    if isinstance(rigid_affine_similarity_transform_sitk, sitk.Euler3DTransform):
        print("\t\t\tangle_x, angle_y, angle_z = " + str(parameters[0:3]) + " rad")
        # print("\t\t\tangle_x, angle_y, angle_z = " + str(parameters[0:3]*180/np.pi) + " deg")
    
    elif isinstance(rigid_affine_similarity_transform_sitk, sitk.Euler2DTransform):
        print("\t\t\tangle = " + str(parameters[0]) + " rad")
        # print("\t\t\tangle = " + str(parameters[0]*180/np.pi) + " deg")

    elif isinstance(rigid_affine_similarity_transform_sitk, sitk.Similarity2DTransform):
        print("\t\t\tangle = " + str(parameters[1]) + " rad")
        print("\t\t\tscale = " + str(rigid_affine_similarity_transform_sitk.GetScale()))

    elif isinstance(rigid_affine_similarity_transform_sitk, sitk.Similarity3DTransform):
        print("\t\t\tangle_x, angle_y, angle_z = " + str(parameters[1:4]) + " rad")
        print("\t\t\tscale = " + str(rigid_affine_similarity_transform_sitk.GetScale()))

    print("\t\t\ttranslation = " + str(translation))
    
    # elif isinstance(rigid_affine_similarity_transform_sitk, sitk.AffineTransform):
    print("\t\t\tmatrix = ")
    for i in range(0, dim):
        print("\t\t\t\t" + str(matrix[i,:]))



def plot_compare_sitk_2D_images(image0_2D_sitk, image1_2D_sitk, fig_number=1, flag_continue=0):

    fig = plt.figure(fig_number)
    plt.suptitle("intensity error norm = " + str(np.linalg.norm(sitk.GetArrayFromImage(image0_2D_sitk-image1_2D_sitk))))
    
    plt.subplot(1,3,1)
    plt.imshow(sitk.GetArrayFromImage(image0_2D_sitk), cmap="Greys_r")
    plt.title("image_0")
    plt.axis('off')

    plt.subplot(1,3,2)
    plt.imshow(sitk.GetArrayFromImage(image1_2D_sitk), cmap="Greys_r")
    plt.title("image_1")
    plt.axis('off')
    
    plt.subplot(1,3,3)
    plt.imshow(sitk.GetArrayFromImage(image0_2D_sitk-image1_2D_sitk), cmap="Greys_r")
    plt.title("image_0 - image_1")
    plt.axis('off')

    ## Plot immediately or wait for following figures to come as well
    if flag_continue == 0:
        plt.show()
    else:
        plt.show(block=False)       # does not pause, but needs plt.show() at end 
                                    # of file to be visible
    return fig


##
#       Plot slices of stack separately
# \date       2016-11-06 01:49:21+0000
#
# \param      stack_sitk  sitk.Image object to be plotted
# \param      cmap        Color map "Greys_r", "jet", etc.
# \param      title       The title
#
def plot_stack_of_slices(stack_sitk, cmap="Greys_r", title="slice"):
    nda = sitk.GetArrayFromImage(stack_sitk)
    ph.plot_3D_array_slice_by_slice(nda, cmap=cmap, title=title)


def plot_slices(slices, cmap="Greys_r", title="slice"):
    N = len(slices)
    nda0 = sitk.GetArrayFromImage(slices[0].sitk)

    nda = np.zeros((N, nda0.shape[0], nda0.shape[1]))
    nda[0,:,:] = nda0
    for i in range(1, N):
        nda[i,:,:] = sitk.GetArrayFromImage(slices[i].sitk)

    ph.plot_3D_array_slice_by_slice(nda, cmap=cmap, title=title)


##
#       Show image with ITK-Snap. Image is saved to /tmp/ for that
#             purpose.
# \date       2016-09-19 16:47:18+0100
#
# \param[in]  image_sitk    either single sitk.Image or list of sitk.Images to
#                           overlay
# \param[in]  title         filename or list of filenames
# \param[in]  segmentation  sitk.Image used as segmentation
#
def show_sitk_image(image_sitk, title="test", segmentation=None, show_comparison_file=False):
    
    dir_output = "/tmp/"
    # cmd = "fslview " + dir_output + title + ".nii.gz & "

    if type(image_sitk) is not list:
        image_sitk = [image_sitk]

    if type(title) is not list:
        title = [title]

    ## Write image
    sitk.WriteImage(image_sitk[0], dir_output + title[0] + ".nii.gz")

    cmd = "itksnap " \
        + "-g " + dir_output + title[0] + ".nii.gz " \
    
    ## Add overlays
    if len(image_sitk)>1:
        overlay_txt = ""

        for i in range(1, len(image_sitk)):
            if len(title) is len(image_sitk):
                sitk.WriteImage(image_sitk[i], dir_output + title[i] + ".nii.gz")
                overlay_txt += dir_output + title[i] + ".nii.gz "
            else:
                sitk.WriteImage(image_sitk[i], dir_output + title[0] + "_overlay" + str(i) + ".nii.gz")
                overlay_txt += dir_output + title[0] + "_overlay" + str(i) + ".nii.gz "
                
        cmd += "-o " + overlay_txt \

    ## Add segmentation
    if segmentation is not None:
        sitk.WriteImage(segmentation, dir_output + title[0] + "_segmentation.nii.gz")
        cmd += "-s " + dir_output + title[0] + "_segmentation.nii.gz " \

    ## Add termination and print command
    cmd += "& "
    print cmd

    ## Execute command
    os.system(cmd)

    ## Create python script for the command above
    if show_comparison_file:
        ## Build executable file containing the information
        now = datetime.datetime.now()
        date_time = str(now.year) + "-" + str(now.month).zfill(2) + "-"  + str(now.day).zfill(2) + " "
        date_time += str(now.hour).zfill(2) + ":" + str(now.minute).zfill(2) + ":" + str(now.second).zfill(2)
        
        call  = "#!/usr/bin/python\n"
        call += "\n"
        call += "##\n"
        call += "#  \\file showComparison.py\n"
        call += "#  \\author Michael Ebner (michael.ebner.14@ucl.ac.uk)\n"
        call += "#  " + date_time + "\n"
        call += "\n"
        call += "import os" 
        call += "\n"
        call += "directory = " + '"' + dir_output + '"'
        call += "\n"
        call += "cmd = " + '"' + re.sub(dir_output, '" + directory + "', cmd) + '" '
        call += "\n"
        call += "print(cmd); os.system(cmd)"

        ## Write function call to python file
        text_file = open("/tmp/showComparison.py", "w")
        text_file.write("%s" % call)
        text_file.close()

        ## Make python file executable
        os.system("chmod +x /tmp/showComparison.py")

##
#       Visualize a list of Stack objects.
# \date       2016-11-05 23:18:23+0000
#
# \param      stacks        List of stack objects
# \param      segmentation  Stack containing the desired segmentation.
#
def show_stacks(stacks, segmentation=None, show_comparison_file=False):

    N_stacks = len(stacks)
    images_sitk = [None]*N_stacks
    titles = [None]*N_stacks

    for i in range(0, N_stacks):
        images_sitk[i] = stacks[i].sitk
        titles[i] = stacks[i].get_filename()

    if segmentation is not None:
        segmentation_sitk = segmentation.sitk_mask

    else:
        segmentation_sitk = None

    show_sitk_image(images_sitk, titles, segmentation_sitk, show_comparison_file)


## Show image with ITK-Snap. Image is saved to /tmp/ for that purpose
#  \param[in] image_itk image to show as itk.object
#  \param[in] segmentation as itk.image object
#  \param[in] overlay image which shall be overlayed onto image_itk (optional)
#  \param[in] title filename for file written to /tmp/ (optional)
def show_itk_image(image_itk, segmentation=None, overlay=None, title="test"):
    
    dir_output = "/tmp/"
    # cmd = "fslview " + dir_output + title + ".nii.gz & "

    if overlay is not None and segmentation is None:
        write_itk_image(image_itk, dir_output + title + ".nii.gz")
        write_itk_image(overlay, dir_output + title + "_overlay.nii.gz")

        cmd = "itksnap " \
            + "-g " + dir_output + title + ".nii.gz " \
            + "-o " + dir_output + title + "_overlay.nii.gz " \
            "& "
    
    elif overlay is None and segmentation is not None:
        write_itk_image(image_itk, dir_output + title + ".nii.gz")
        write_itk_image(segmentation, dir_output + title + "_segmentation.nii.gz")

        cmd = "itksnap " \
            + "-g " + dir_output + title + ".nii.gz " \
            + "-s " + dir_output + title + "_segmentation.nii.gz " \
            + "& "

    elif overlay is not None and segmentation is not None:
        write_itk_image(image_itk, dir_output + title + ".nii.gz")
        write_itk_image(segmentation, dir_output + title + "_segmentation.nii.gz")
        write_itk_image(overlay, dir_output + title + "_overlay.nii.gz")

        cmd = "itksnap " \
            + "-g " + dir_output + title + ".nii.gz " \
            + "-s " + dir_output + title + "_segmentation.nii.gz " \
            + "-o " + dir_output + title + "_overlay.nii.gz " \
            + "& "

    else:
        write_itk_image(image_itk, dir_output + title + ".nii.gz")

        cmd = "itksnap " \
            + "-g " + dir_output + title + ".nii.gz " \
            "& "

    os.system(cmd)


##
# Gets the downsampled sitk image.
# \date       2016-11-21 20:50:59+0000
#
# \param      image_sitk            The image sitk
# \param      downsampling_factors  The downsampling factors in x,y and z
#                                   direction as tuple
# \param      interpolator          The interpolator
# \param      default_pixel_value   The default pixel value
# \param      new_spacing           The new spacing in x, y and z as tuple
#
# \return     The downsampled sitk image.
#
def get_downsampled_sitk_image(image_sitk, downsampling_factors=(1,1,1), interpolator="NearestNeighbor", default_pixel_value=0.0, new_spacing=None):

    ## Read required information from original image:
    dimension = image_sitk.GetDimension()
    spacing = np.array(image_sitk.GetSpacing()).astype('double')
    size = np.array(image_sitk.GetSize()).astype("int")

    if new_spacing is not None:
        downsampling_factors = new_spacing/spacing

    else:
        ## Convert to array
        downsampling_factors = np.array(downsampling_factors).astype('double')

    ## Choose interpolator
    try:
        interpolator_str = interpolator
        interpolator = eval("sitk.sitk" + interpolator_str)
    except:
        raise ValueError("Error: interpolator is not known")

    ## Define new image space
    spacing_new = spacing*downsampling_factors[0:dimension]
    size_new = np.round(size/downsampling_factors[0:dimension]).astype("int")

    ## Resampling
    image_sitk_resampled = sitk.Resample(image_sitk, size_new, eval("sitk.Euler" + str(dimension) + "DTransform()"), interpolator, image_sitk.GetOrigin(), spacing_new, image_sitk.GetDirection(), default_pixel_value, image_sitk.GetPixelIDValue())

    return image_sitk_resampled


##
# Gets the enlarged sitk image.
# \date       2016-11-27 15:46:44+0000
#
# \param      image_sitk  The image sitk
# \param      frame       Extra frame (in voxels) in each direction (or only in
#                         i-direction if the others are specified)
# \param      frame_j     Extra frame (in voxels) in j-direction
# \param      frame_k     Extra frame (in voxels) in j-direction
#
# \return     The enlarged sitk image.
#
def get_enlarged_sitk_image(image_sitk, frame=0, frame_j=None, frame_k=None):

    size = np.array(image_sitk.GetSize())
    origin = np.array(image_sitk.GetOrigin())
    spacing = np.array(image_sitk.GetSpacing())
    dimension = image_sitk.GetDimension()

    if frame_j is None:
        frame_j = frame
    if frame_k is None:
        frame_k = frame

    ## Compute new size of enlarged stack
    size[0] += 2*frame
    size[1] += 2*frame_j
    if dimension is 3:
        size[2] += 2*frame_k
    
    ## Compute translation of enlarged stack by considering additional extra_frame
    a_x = image_sitk.TransformIndexToPhysicalPoint((1,0,0)) - origin
    a_y = image_sitk.TransformIndexToPhysicalPoint((0,1,0)) - origin
    e_x = a_x/np.linalg.norm(a_x)
    e_y = a_y/np.linalg.norm(a_y)
    translation = e_x*frame*spacing[0] + e_y*frame_j*spacing[1]

    if dimension is 3:
        a_z = image_sitk.TransformIndexToPhysicalPoint((0,0,1)) - origin
        e_z = a_z/np.linalg.norm(a_z)
        translation += e_z*frame_k*spacing[2]
        
    origin -= translation

    ## Resample
    image_enlarged_sitk = sitk.Resample(image_sitk, size, eval("sitk.Euler" + str(dimension) +"DTransform()"), sitk.sitkNearestNeighbor, origin, spacing, image_sitk.GetDirection(), 0.0, image_sitk.GetPixelIDValue())

    return image_enlarged_sitk